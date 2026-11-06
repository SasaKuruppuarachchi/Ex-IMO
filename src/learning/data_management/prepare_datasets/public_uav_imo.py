"""
Convert the four cleaned UAV datasets to IMO's HDF5 format, adding the Ex-IMO torque features.

    docker/run.sh python3 src/learning/data_management/prepare_datasets/public_uav_imo.py --dataset all

Input (read-only):
    data/processed/{nanobench,tii_ratm,neurobem}/<seq>/processed_data/<split>/data.hdf5
    data/clean/ai_io/datasets/our2/<seq>/processed_data/<split>/data[__partK].hdf5
Output, at 100 Hz:
    <out>/<dataset>/<seq>/<split>[__partK]/data.hdf5 + stamped_groundtruth_imu.txt
    <out>/<dataset>/{train,val,test}.txt, plus unseen.txt for AI-IO's patterned flights
    <out>/<dataset>/physics.json and config/physics/<dataset>.json

Keys as IMO (prepare_datasets/blackbird.py): ts, gyro_raw, accel_raw, gyro_calib, accel_calib, gyro_bias,
accel_bias, thrust and i_thrust [0, 0, T] in m/s^2, traj_target [p, q xyzw], traj_target_oris_from_imu (a
placeholder, as upstream). Added: tau_gyro, tau_rotor (see below), traj_target_v [v_world].

All frames are FLU body and z-up world, so thrust is +z, unlike Blackbird's -z.

Collective thrust. No dataset documents kf, and mass is known for two of the four (see docs/EX_IMO.md),
so the mass-normalised map is fitted per platform on the TRAINING split, against the inverse-dynamics
specific force f_z = e_z^T R^T (dv/dt + g e_z) from ground truth:
    T = sum_i f_i,   f_i = a u_i^2 + b u_i,   u_i = rotor signal delayed by L, optionally x vbat / vbat_ref
The candidates are compared on the validation split. Inverse dynamics is only ever the fitting target:
it uses the displacement the network predicts, so it can't be an input. The delay is causal. It models the
motor response on the two datasets that log commands instead of rotor speeds (scripts/diag/rotor_gyro_lag.py).

Body torque, normalised by inertia, in rad/s^2 and divided by a dataset-wide scale:
    tau = J^-1 (J dw/dt + w x J w) = dw/dt + [c_x w_y w_z, c_y w_z w_x, c_z w_x w_y]
    c_x = (J_z - J_y) / J_x, c_y = (J_x - J_z) / J_y, c_z = (J_y - J_x) / J_z
Only inertia ratios enter. They are published for NeuroBEM; elsewhere they are unknown, and fitting them is
unreliable (rotor_gyro_lag.py), so c = [0.8, -0.8, 0] is assumed, close to NeuroBEM's [0.88, -0.86, -0.09]. Two features:
    tau_gyro   backward difference of the gyro + the gyroscopic term (causal; a function of the gyro history)
    tau_rotor  A f + d, with A, d from least squares of dw/dt + c (w x w) on f on the training split (causal;
               independent of the gyro; the motor order is learned, not assumed). This is the part of the torque
               that rotor differentials explain, not the full torque: R^2 is low on most axes (docs/EX_IMO.md).
"""
import argparse
import glob
import itertools
import json
import os
import re

import h5py
import numpy as np
from scipy.signal import savgol_filter
from scipy.spatial.transform import Rotation

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
from eximo_paths import DATA as OUT, WS
G = 9.81
DATASETS = ("ai_io", "nanobench", "tii_ratm", "neurobem")
# Published inertia, used only to validate the fitted ratios (data/clean/neurobem/Readme.md).
KNOWN_J = {"neurobem": [0.0025, 0.0021, 0.0043]}
ASSUMED_C = [0.8, -0.8, 0.0]
DELAYS = (0, 1, 2, 3, 4, 5)                                                        # samples, at 100 Hz
# AI-IO's patterned flights: no split of them is used for training.
AIIO_PATTERNED = ("indoor/circle", "indoor/eight", "indoor/random", "indoor/updown_circle", "indoor/updown_eight")
# Stage 3, held-out shapes: <dataset>__<fold> leaves these flights out of train and val, and out of the thrust and torque fits.
# NeuroBEM names flights by date, so its patterns match the comments in Flights.txt.
FOLDS = {"tii_ratm": {"ellipse": "ellipse", "lemniscate": "lemniscate", "trackRATM": "trackRATM"},
         "nanobench": {"crossing": "figure8|star|trefoil", "round": "circle|oval|helix"},
         "neurobem": {"circles": "circle|ellipse", "lemniscate_cpc": "lemniscate|cpc"}}


# ------------------------------------------------------------------------------- loading
def find_sequences(dataset):
    """[(name, split, path)]. name is unique per file, e.g. indoor/eight/spd_3/test__part1."""
    out = []
    if dataset == "ai_io":
        root = os.path.join(WS, "data", "clean", "ai_io", "datasets", "our2")
    else:
        root = os.path.join(WS, "data", "processed", dataset)
    for f in sorted(glob.glob(os.path.join(root, "**", "processed_data", "*", "data*.hdf5"), recursive=True)):
        seq, rest = os.path.relpath(f, root).split(os.sep + "processed_data" + os.sep)
        split, fn = rest.split(os.sep)
        part = fn[len("data"):-len(".hdf5")]                                       # "" or "__partK"
        out.append((os.path.join(seq, split + part), split, f))
    return out


def flight_label(dataset, seq):
    """The text a fold pattern matches for a flight, e.g. indoor seq names or NeuroBEM's Flights.txt comment."""
    if dataset != "neurobem":
        return seq
    with open(os.path.join(WS, "data", "clean", "neurobem", "Flights.txt")) as f:
        comments = dict(re.findall(r'"([0-9-]+)";\s*%\s*(.*)', f.read()))
    return comments[seq.split("_seg_")[0]]


def is_held_out(dataset, fold, name):
    return fold is not None and re.search(FOLDS[dataset][fold], flight_label(dataset, name.rsplit(os.sep, 1)[0])) is not None


def load_sequence(path):
    with h5py.File(path, "r") as f:
        s = dict(ts=f["ts"][()], acc=f["accel_raw"][()], gyro=f["gyro_raw"][()], acc_calib=f["accel_calib"][()],
                 gyro_calib=f["gyro_calib"][()], rotors=f["rotor_spd"][()], traj=f["traj_target"][()],
                 ba=f["accel_bias"][()], bg=f["gyro_bias"][()])
        s["vbat"] = f["vbat"][()] if "vbat" in f else None
    s["R"] = Rotation.from_quat(s["traj"][:, 3:7]).as_matrix()
    return s


def smooth(x):
    return savgol_filter(x, 21, 3, axis=0)


def inverse_dynamics(s):
    """Ground-truth specific force in the body frame and the smoothed body rate derivative."""
    dt = np.median(np.diff(s["ts"]))
    acc_w = savgol_filter(s["traj"][:, 7:10], 21, 3, deriv=1, delta=dt, axis=0)
    f_b = np.einsum("nij,ni->nj", s["R"], acc_w + np.array([0.0, 0.0, G]))  # R^T
    dw = savgol_filter(s["gyro_calib"], 21, 3, deriv=1, delta=dt, axis=0)
    return f_b, dw


def flying_mask(s, u):
    """Excludes pre-takeoff and landing: on the ground the rotor model is not the force balance."""
    z = s["traj"][:, 2]
    return (u.min(axis=1) > 0.05 * np.percentile(u, 99)) & (z > np.percentile(z, 1) + 0.1)


# ---------------------------------------------------------------------------- thrust model
def rotor_signal(s, use_vbat, vref, delay=0):
    u = s["rotors"] * (s["vbat"][:, None] / vref if use_vbat else 1.0)
    if delay:
        u = np.r_[np.repeat(u[:1], delay, axis=0), u[:-delay]]
    return u


def design(u, kind):
    if kind == "quad":
        return (u ** 2).sum(axis=1, keepdims=True)
    return np.stack([(u ** 2).sum(axis=1), u.sum(axis=1)], axis=1)                # quad+lin


def per_motor_thrust(u, coef, kind):
    return coef[0] * u ** 2 + (coef[1] * u if kind != "quad" else 0.0)


def fit_thrust(train, val, has_vbat):
    """Least squares on the smoothed signals. Returns the candidate with the lowest validation RMSE."""
    vrefs = np.concatenate([s["vbat"] for s in train]).mean() if has_vbat else 1.0
    cands = []
    for kind, use_vbat, delay in itertools.product(("quad", "quad+lin"), (False, True) if has_vbat else (False,), DELAYS):
        scale = 1.0 / np.percentile(np.concatenate([rotor_signal(s, use_vbat, vrefs) for s in train]), 99)

        def xy(seqs):
            X, y = [], []
            for s in seqs:
                u = rotor_signal(s, use_vbat, vrefs, delay) * scale
                m = flying_mask(s, u)
                X.append(smooth(design(u, kind))[m])
                y.append(inverse_dynamics(s)[0][m, 2])
            return np.concatenate(X), np.concatenate(y)

        X, y = xy(train)
        coef = np.linalg.lstsq(X, y, rcond=None)[0]
        Xv, yv = xy(val)
        res = yv - Xv @ coef
        cands.append(dict(kind=kind, use_vbat=use_vbat, delay=delay, vbat_ref=float(vrefs), u_scale=float(scale),
                          coef=coef.tolist(), val_rmse=float(np.sqrt(np.mean(res ** 2))),
                          val_r2=float(1 - res.var() / yv.var()),
                          train_rmse=float(np.sqrt(np.mean((y - X @ coef) ** 2)))))
    best = min(cands, key=lambda c: c["val_rmse"])
    return best, cands


def collective_thrust(s, th):
    u = rotor_signal(s, th["use_vbat"], th["vbat_ref"], th["delay"]) * th["u_scale"]
    return per_motor_thrust(u, th["coef"], th["kind"])


def check_thrust_accel(seqs, th):
    """Independent check: the model against the accelerometer, which the fit did not see."""
    a, t = [], []
    for s in seqs:
        f = collective_thrust(s, th)
        m = flying_mask(s, f)
        a.append(smooth(s["acc_calib"])[m, 2])
        t.append(smooth(f.sum(axis=1))[m])
    a, t = np.concatenate(a), np.concatenate(t)
    return dict(rmse=float(np.sqrt(np.mean((a - t) ** 2))), corr=float(np.corrcoef(a, t)[0, 1]),
                ratio=float((a * t).sum() / (t * t).sum()))


# ---------------------------------------------------------------------------- torque model
def gyroscopic_products(w):
    return np.stack([w[:, 1] * w[:, 2], w[:, 2] * w[:, 0], w[:, 0] * w[:, 1]], axis=1)


def fit_allocation(train, val, th, c):
    """Per axis: dw_k/dt + c_k (w x w)_k = A_k f + d_k, on 70 ms smoothing. Returns A, d, validation R^2."""
    def xy(seqs):
        F, Y = [], []
        for s in seqs:
            f = collective_thrust(s, th)
            m = flying_mask(s, f)
            dt = np.median(np.diff(s["ts"]))
            w = savgol_filter(s["gyro_calib"], 7, 3, axis=0)
            dw = savgol_filter(s["gyro_calib"], 7, 3, deriv=1, delta=dt, axis=0)
            F.append(savgol_filter(f, 7, 3, axis=0)[m])
            Y.append((dw + c * gyroscopic_products(w))[m])
        return np.c_[np.concatenate(F), np.ones(sum(len(x) for x in F))], np.concatenate(Y)

    X, Y = xy(train)
    Xv, Yv = xy(val)
    sol = np.linalg.lstsq(X, Y, rcond=None)[0]                                     # 5 x 3
    res = Yv - Xv @ sol
    return sol[:4].T, sol[4], (1 - res.var(axis=0) / Yv.var(axis=0)).tolist()


def torque_features(s, th, phys):
    """Causal torque features. J^-1 tau in rad/s^2 / tau_scale."""
    w = s["gyro_calib"]
    dw = np.zeros_like(w)
    dw[1:] = (w[1:] - w[:-1]) / np.diff(s["ts"])[:, None]
    dw[0] = dw[1]
    c = np.asarray(phys["gyroscopic_c"])
    tau_gyro = (dw + c * gyroscopic_products(w)) / phys["tau_scale"]
    f = collective_thrust(s, th)
    tau_rotor = (f @ np.asarray(phys["alloc_A"]).T + np.asarray(phys["alloc_d"])) / phys["tau_scale"]
    return tau_gyro, tau_rotor


# ------------------------------------------------------------------------------- writing
def write_sequence(s, name, out_root, th, phys):
    d = os.path.join(out_root, name)
    os.makedirs(d, exist_ok=True)
    T = collective_thrust(s, th).sum(axis=1)
    thrust = np.zeros((len(T), 3))
    thrust[:, 2] = T
    tau_gyro, tau_rotor = torque_features(s, th, phys)
    with h5py.File(os.path.join(d, "data.hdf5"), "w") as f:
        f["ts"] = s["ts"]
        f["gyro_raw"] = s["gyro"]
        f["accel_raw"] = s["acc"]
        f["gyro_calib"] = s["gyro_calib"]
        f["accel_calib"] = s["acc_calib"]
        f["gyro_bias"] = s["bg"]
        f["accel_bias"] = s["ba"]
        f["thrust"] = thrust
        f["i_thrust"] = thrust
        f["tau_gyro"] = tau_gyro
        f["tau_rotor"] = tau_rotor
        f["traj_target"] = s["traj"][:, :7]
        f["traj_target_v"] = s["traj"][:, 7:10]
        f["traj_target_oris_from_imu"] = s["traj"][:1]                             # placeholder, as upstream
    np.savetxt(os.path.join(d, "stamped_groundtruth_imu.txt"), np.c_[s["ts"], s["traj"]],
               header="ts x y z qx qy qz qw vx vy vz", fmt="%.6f")


def convert(dataset, out, fold=None):
    seqs = find_sequences(dataset)
    by = {sp: [load_sequence(p) for n, split, p in seqs if split == sp and not is_held_out(dataset, fold, n)] for sp in ("train", "val")}
    has_vbat = all(s["vbat"] is not None for s in by["train"])

    # Windows shorter than the smoothing kernel cannot be fitted on.
    train = [s for s in by["train"] if len(s["ts"]) > 21]
    val = [s for s in by["val"] if len(s["ts"]) > 21]
    th, cands = fit_thrust(train, val, has_vbat)
    if dataset in KNOWN_J:
        Jx, Jy, Jz = KNOWN_J[dataset]
        c = np.array([(Jz - Jy) / Jx, (Jx - Jz) / Jy, (Jy - Jx) / Jz])
    else:
        c = np.array(ASSUMED_C)
    A, d, r2 = fit_allocation(train, val, th, c)

    dt_rms = np.concatenate([np.diff(s["gyro_calib"], axis=0) / np.diff(s["ts"])[:, None] for s in train])
    phys = dict(dataset=dataset, thrust=th, thrust_candidates=cands, thrust_vs_accel_val=check_thrust_accel(val, th),
                alloc_A=A.tolist(), alloc_d=d.tolist(), gyroscopic_c=c.tolist(), gyroscopic_c_source=
                "published J" if dataset in KNOWN_J else "assumed", alloc_val_r2=r2,
                tau_scale=float(np.sqrt(np.mean(dt_rms ** 2))),
                hover_thrust_check=float(np.median(np.concatenate(
                    [collective_thrust(s, th).sum(axis=1) for s in val]))))

    tag = f"{dataset}__{fold}" if fold else dataset
    root = os.path.join(out, tag)
    lists = {}
    for name, split, path in seqs:
        s = load_sequence(path)
        write_sequence(s, name, root, th, phys)
        seq = name.rsplit(os.sep, 1)[0]
        unseen = is_held_out(dataset, fold, name) or (dataset == "ai_io" and seq.startswith(AIIO_PATTERNED))
        lists.setdefault("unseen" if unseen else split, []).append(name)
    os.makedirs(root, exist_ok=True)
    for k, names in lists.items():
        with open(os.path.join(root, k + ".txt"), "w") as f:
            f.write("\n".join(names) + "\n")
    phys["split_counts"] = {k: len(v) for k, v in lists.items()}
    for fn in (os.path.join(root, "physics.json"), os.path.join(REPO, "config", "physics", tag + ".json")):
        os.makedirs(os.path.dirname(fn), exist_ok=True)
        with open(fn, "w") as f:
            json.dump(phys, f, indent=1)
    return phys


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", default="all", choices=("all",) + DATASETS)
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--folds", action="store_true", help="write the held-out-shape folds of the dataset instead")
    a = ap.parse_args()
    jobs = [(ds, None) for ds in (DATASETS if a.dataset == "all" else (a.dataset,))]
    if a.folds:
        jobs = [(ds, k) for ds, _ in jobs for k in FOLDS.get(ds, ())]
    for ds, fold in jobs:
        p = convert(ds, a.out, fold)
        th = p["thrust"]
        print(f"\n== {ds} {fold or ''}: {p['split_counts']}")
        print(f"   thrust {th['kind']} vbat={th['use_vbat']} delay={th['delay'] * 10} ms: val RMSE {th['val_rmse']:.3f} m/s^2, R2 {th['val_r2']:.3f}; "
              f"vs accel {p['thrust_vs_accel_val']}")
        for c in p["thrust_candidates"]:
            if c["delay"] == th["delay"]:
                print(f"     {c['kind']:9s} vbat={c['use_vbat']!s:5s} train {c['train_rmse']:.3f} val {c['val_rmse']:.3f}")
        print(f"   alloc val R2 {np.round(p['alloc_val_r2'], 3).tolist()}, tau_scale {p['tau_scale']:.1f} rad/s^2")
        print(f"   A (rad/s^2 per m/s^2):\n{np.round(p['alloc_A'], 2)}")
        print(f"   gyroscopic c {np.round(p['gyroscopic_c'], 3).tolist()} ({p['gyroscopic_c_source']})")


if __name__ == "__main__":
    main()
