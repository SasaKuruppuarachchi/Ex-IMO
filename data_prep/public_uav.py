"""
Convert the cleaned NanoBench, TII-RATM and NeuroBEM data (data/clean/, see data/CLEANING.md)
into AI-IO's processed format, so that training, testing and the EKF run unchanged:

    <out>/<dataset>/<sequence>/processed_data/<split>/data.hdf5 + stamped_groundtruth_imu.txt

    python3 data_prep/public_uav.py --dataset all

AI-IO needs no conversion: its cleaned copy is already in this format (data/clean/ai_io/datasets/our2).
The splits are fixed by shape (split_* below), so every method is compared on the same flights.

HDF5 keys as AI-IO (prepare_datasets/our2.py), 100 Hz:
    ts [s], accel_raw/accel_calib [m/s^2, body specific force], gyro_raw/gyro_calib [rad/s, body],
    rotor_spd [4, the platform's actuation signal], throttle [zeros], gyro_bias/accel_bias [zeros],
    traj_target [p_world(3), q_body->world xyzw(4), v_world(3)]

Frame conventions, verified against each dataset's own ground truth (gyro vs the body rate of the
ground-truth attitude, accelerometer vs R^T (dv/dt + g), velocity vs dp/dt); the same checks run on
the converted output and are written to <out>/<dataset>/conversion_report.json:
    NanoBench  accelerometer in g -> x 9.81; quaternion xyzw body->world; velocity world.
    TII-RATM   drone_rot[0..8] is the body->world matrix stored column-major; velocity world;
               drone_velocity_angular_* is not the body rate and is not used.
    NeuroBEM   velocity is body-frame -> rotated to world; acc is body specific force; vbat logged in 0.1 V.
Resampling [choice]: TII (500 Hz) and NeuroBEM (400 Hz) are decimated onto the 10 ms grid (every
5th / 4th row of the already uniformly resampled CSVs), as AI-IO resamples its own IMU onto a
100 Hz grid. NanoBench is already at 100 Hz.
"""
import argparse
import glob
import json
import os
import re

import h5py
import numpy as np
import pandas as pd
from scipy.signal import savgol_filter
from scipy.spatial.transform import Rotation

G = 9.81
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.environ.get("EXIMO_WORKSPACE", "/workspace")                           # holds data/{raw,clean,processed}
CLEAN = os.environ.get("EXIMO_CLEAN", os.path.join(REPO, "data", "clean"))


# ----------------------------------------------------------------------------- loaders
def _seq(name, t, acc, gyro, act, pos, quat, vel, source, vbat=None):
    return dict(name=name, ts=np.asarray(t, float), acc=np.asarray(acc, float), gyro=np.asarray(gyro, float),
                act=np.asarray(act, float), pos=np.asarray(pos, float), quat=np.asarray(quat, float),
                vel=np.asarray(vel, float), source=source, vbat=None if vbat is None else np.asarray(vbat, float))


def load_nanobench():
    out = []
    for f in sorted(glob.glob(os.path.join(CLEAN, "nanobench", "*.csv"))):
        d = pd.read_csv(f)
        out.append(_seq(os.path.basename(f)[:-4], d.t, d[["imu_acc_x", "imu_acc_y", "imu_acc_z"]].values * G,
                        d[["imu_gyro_x", "imu_gyro_y", "imu_gyro_z"]].values,
                        d[[f"motor_motor_m{i}" for i in range(1, 5)]].values,
                        d[["px", "py", "pz"]].values, d[["qx", "qy", "qz", "qw"]].values, d[["vx", "vy", "vz"]].values,
                        os.path.relpath(f, REPO), vbat=d["pwr_pm_vbat"].values))
    return out


def load_tii(modes=("autonomous",)):
    out = []
    for mode in modes:
        for f in sorted(glob.glob(os.path.join(CLEAN, "tii_ratm", mode, "flight-*", "*_500hz_freq_sync.csv"))):
            d = pd.read_csv(f).iloc[::5].reset_index(drop=True)                    # 500 Hz -> 100 Hz
            rot = d[[f"drone_rot[{i}]" for i in range(9)]].values.reshape(-1, 3, 3).transpose(0, 2, 1)
            out.append(_seq(os.path.basename(f).split("_500hz")[0], d.elapsed_time,
                            d[["accel_x", "accel_y", "accel_z"]].values, d[["gyro_x", "gyro_y", "gyro_z"]].values,
                            d[[f"thrust[{i}]" for i in range(4)]].values, d[["drone_x", "drone_y", "drone_z"]].values,
                            Rotation.from_matrix(rot).as_quat(),
                            d[["drone_velocity_linear_x", "drone_velocity_linear_y", "drone_velocity_linear_z"]].values,
                            os.path.relpath(f, REPO), vbat=d["vbat"].values))
    return out


def load_neurobem():
    out = []
    for f in sorted(glob.glob(os.path.join(CLEAN, "neurobem", "processed_data", "merged_*.csv"))):
        d = pd.read_csv(f)
        d.columns = [c.strip() for c in d.columns]
        d = d.iloc[::4].reset_index(drop=True)                                     # 400 Hz -> 100 Hz
        q = d[["quat x", "quat y", "quat z", "quat w"]].values
        v_world = Rotation.from_quat(q).apply(d[["vel x", "vel y", "vel z"]].values)
        out.append(_seq(os.path.basename(f)[len("merged_"):-4], d.t, d[["acc x", "acc y", "acc z"]].values,
                        d[["ang vel x", "ang vel y", "ang vel z"]].values, d[[f"mot {i}" for i in range(1, 5)]].values,
                        d[["pos x", "pos y", "pos z"]].values, q, v_world, os.path.relpath(f, REPO),
                        vbat=d["vbat"].values / 10.0))                              # logged in 0.1 V (4S pack)
    return out


# ------------------------------------------------------------------------------ splits
def split_nanobench(names):
    """test = 3 per main shape + 4 others (22), val = 4, rest train."""
    groups = {}
    for n in names:
        m = re.match(r"(.+)_rep(\d+)$", n)
        groups.setdefault(m.group(1), []).append((int(m.group(2)), n))
    for g in groups.values():
        g.sort()
    split = {n: "train" for n in names}
    for shape in ("B2_circle", "B3_figure8", "B5_helix", "B7_oval", "B8_star", "B9_trefoil"):
        for speed in ("slow", "medium", "fast"):
            reps = groups.get(f"{shape}_{speed}", [])
            if reps:
                split[reps[-1][1]] = "test"                                        # highest-numbered take
    for other in ("B6_linear_ramp", "B10_lissajous_fast", "B11_random_waypoints", "B12_staircase_climb"):
        split[groups[other][-1][1]] = "test"
    for shape in ("B2_circle", "B3_figure8", "B7_oval", "B8_star"):
        split[groups[f"{shape}_medium"][-2][1]] = "val"                           # second-highest medium take
    return split


def split_tii(names):
    """Per track type (ellipse 01-06, lemniscate 07-12, trackRATM 13-18): 1-3 train, 4 val, 5-6 test."""
    split = {}
    for n in names:
        k = (int(re.match(r"flight-(\d+)", n).group(1)) - 1) % 6
        split[n] = "train" if k < 3 else "val" if k == 3 else "test"
    return split


def split_neurobem(names):
    """Test = the authors' testset.txt; other segments of test flights excluded; every 5th remaining
    flight (sorted) -> val, rest -> train."""
    test = {l.strip() for l in open(os.path.join(CLEAN, "neurobem", "testset.txt")) if l.strip()}
    flight = lambda n: n.rsplit("_seg_", 1)[0]
    test_flights = {flight(n) for n in test}
    others = sorted({flight(n) for n in names} - test_flights)
    val_flights = set(others[2::5])
    split = {}
    for n in names:
        if n in test:
            split[n] = "test"
        elif flight(n) in test_flights:
            split[n] = None                                                        # excluded: same flight as a test segment
        else:
            split[n] = "val" if flight(n) in val_flights else "train"
    return split


DATASETS = {
    "nanobench": dict(load=load_nanobench, split=split_nanobench, actuation="motor PWM 0-65535 (m1..m4)"),
    "tii_ratm": dict(load=load_tii, split=split_tii, actuation="normalised thrust command [0,1] (thrust[0..3])"),
    "neurobem": dict(load=load_neurobem, split=split_neurobem, actuation="motor speed rad/s (mot 1..4)"),
}


# ------------------------------------------------------------------------------ checks
def frame_check(s):
    """Correlation per axis of gyro vs ground-truth body rate, accel vs ground-truth specific force, and
    velocity vs d(position)/dt. All three ~1 (velocity) / clearly positive (inertial) if frames agree."""
    t = s["ts"]
    if len(t) < 50:
        return None
    sm = lambda x: savgol_filter(x, 21, 3, axis=0)
    R = Rotation.from_quat(s["quat"])
    w_gt = (R[:-1].inv() * R[1:]).as_rotvec() / np.diff(t)[:, None]
    f_gt = R.inv().apply(np.gradient(sm(s["vel"]), t, axis=0) + np.array([0, 0, G]))
    v_fd = np.gradient(sm(s["pos"]), t, axis=0)
    corr = lambda a, b: [round(float(np.corrcoef(a[:, i], b[:, i])[0, 1]), 3) for i in range(3)]
    return dict(gyro=corr(sm(s["gyro"])[:-1], sm(w_gt)), accel=corr(sm(s["acc"]), f_gt), velocity=corr(s["vel"], v_fd))


# ------------------------------------------------------------------------------ writing
def write_sequence(s, split, root):
    d = os.path.join(root, s["name"], "processed_data", split)
    os.makedirs(d, exist_ok=True)
    n = len(s["ts"])
    traj = np.concatenate([s["pos"], s["quat"], s["vel"]], axis=1)
    with h5py.File(os.path.join(d, "data.hdf5"), "w") as f:
        f["ts"] = s["ts"]
        f["gyro_raw"] = s["gyro"]
        f["accel_raw"] = s["acc"]
        f["gyro_calib"] = s["gyro"]
        f["accel_calib"] = s["acc"]
        f["gyro_bias"] = np.zeros(3)
        f["accel_bias"] = np.zeros(3)
        f["throttle"] = np.zeros((n, 1))
        f["rotor_spd"] = s["act"]
        f["traj_target"] = traj
        if s.get("vbat") is not None:
            f["vbat"] = s["vbat"]                                                  # battery voltage [V]
        f.attrs["source"] = s["source"]
    np.savetxt(os.path.join(d, "stamped_groundtruth_imu.txt"), np.concatenate([s["ts"][:, None], traj], axis=1),
               header="ts x y z qx qy qz qw vx vy vz", fmt="%.6f")


def split_counts(split):
    return {k: sum(1 for sp in split.values() if sp == k) for k in ("train", "val", "test")}


def _natural(s):
    return [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", s)]


def convert(dataset, out):
    spec = DATASETS[dataset]
    seqs = spec["load"]()
    split = spec["split"]([s["name"] for s in seqs])
    root = os.path.join(out, dataset)
    report = dict(dataset=dataset, actuation=spec["actuation"], rate_hz=100, sequences={})
    for s in seqs:
        sp = split[s["name"]]
        dt = np.diff(s["ts"])
        info = dict(split=sp, source=s["source"], samples=len(s["ts"]), duration_s=round(float(s["ts"][-1] - s["ts"][0]), 2),
                    dt_median=round(float(np.median(dt)), 5), max_speed=round(float(np.linalg.norm(s["vel"], axis=1).max()), 2))
        if sp is not None:
            write_sequence(s, sp, root)
            info["frame_check"] = frame_check(s)
        report["sequences"][s["name"]] = info
    counts = split_counts(split)
    report["split_counts"] = counts
    report["excluded"] = sorted(k for k, v in split.items() if v is None)
    with open(os.path.join(root, "conversion_report.json"), "w") as f:
        json.dump(report, f, indent=1)
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", default="all", choices=["all"] + list(DATASETS))
    ap.add_argument("--out", default=os.path.join(REPO, "data", "processed"))
    a = ap.parse_args()
    for ds in (DATASETS if a.dataset == "all" else [a.dataset]):
        r = convert(ds, a.out)
        checks = [v["frame_check"] for v in r["sequences"].values() if v.get("frame_check")]
        med = {k: np.round(np.median([c[k] for c in checks], axis=0), 2).tolist() for k in ("gyro", "accel", "velocity")}
        dur = {sp: round(sum(v["duration_s"] for v in r["sequences"].values() if v["split"] == sp) / 60, 1) for sp in ("train", "val", "test")}
        vmax = max(v["max_speed"] for v in r["sequences"].values())
        print(f"{ds}: split {r['split_counts']} (minutes {dur}), excluded {len(r['excluded'])}, max speed {vmax} m/s; "
              f"median frame-check corr gyro {med['gyro']} accel {med['accel']} velocity {med['velocity']}")


if __name__ == "__main__":
    main()
