"""The Ex-IMO parts of the filter, end to end, with no trained network: an oracle returns the true displacement."""
import json
import os
import tempfile

import h5py
import numpy as np
import pytest
import torch
from scipy.spatial.transform import Rotation

from filter.python.src.filter_manager import FilterManager
from filter.python.src.scekf import ImuMSCKF
from filter.python.src.utils.dotdict import dotdict
from filter.python.src.utils.math_utils import mat_exp
from learning.data_management.features import build_features, input_dim
from learning.data_management.windows import WindowData
from learning.network.model_factory import get_model

G = 9.81
DT = 0.01


def synthetic_flight(T=20.0):
    """A consistent trajectory: rate-driven attitude, smooth position, IMU derived from them, no noise."""
    t = np.arange(0, T, DT)
    p = np.c_[3 * np.sin(0.7 * t), 2 * np.cos(0.5 * t), 1.5 + 0.5 * np.sin(0.3 * t)]
    v = np.gradient(p, DT, axis=0)
    a = np.gradient(v, DT, axis=0)
    # thrust along body z: attitude from the specific force, plus a yaw rate
    f_w = a + np.array([0, 0, G])
    z = f_w / np.linalg.norm(f_w, axis=1, keepdims=True)
    yaw = 0.3 * t
    x_c = np.c_[np.cos(yaw), np.sin(yaw), np.zeros_like(yaw)]
    y = np.cross(z, x_c)
    y /= np.linalg.norm(y, axis=1, keepdims=True)
    x = np.cross(y, z)
    R = np.stack([x, y, z], axis=2)
    rot = Rotation.from_matrix(R)
    w = (rot[:-1].inv() * rot[1:]).as_rotvec() / DT
    w = np.r_[w, w[-1:]]
    acc = np.einsum("nij,ni->nj", R, f_w)
    return dict(t=t, p=p, v=v, R=R, q=rot.as_quat(), w=w, acc=acc)


def write_sequence(root, s):
    d = os.path.join(root, "synth", "seq")
    os.makedirs(d)
    thrust = np.zeros_like(s["p"])
    thrust[:, 2] = s["acc"][:, 2]
    with h5py.File(os.path.join(d, "data.hdf5"), "w") as f:
        f["ts"] = s["t"]
        for k in ("gyro_raw", "gyro_calib"):
            f[k] = s["w"]
        for k in ("accel_raw", "accel_calib"):
            f[k] = s["acc"]
        f["gyro_bias"] = np.zeros(3)
        f["accel_bias"] = np.zeros(3)
        f["thrust"] = thrust
        f["i_thrust"] = thrust
        f["tau_gyro"] = np.gradient(s["w"], DT, axis=0)
        f["tau_rotor"] = np.gradient(s["w"], DT, axis=0)
        f["traj_target"] = np.c_[s["p"], s["q"]]
        f["traj_target_v"] = s["v"]
    return d


def make_args(root, out, frame, torque="none", **kw):
    model_dir = os.path.join(out, "model")
    os.makedirs(model_dir, exist_ok=True)
    with open(os.path.join(model_dir, "p.json"), "w") as f:
        json.dump(dict(sampling_freq=100.0, window_time=0.5, frame=frame, torque=torque), f)
    torch.save(dict(model_state_dict=get_model(input_dim(torque), 3).state_dict()), os.path.join(model_dir, "c.pt"))
    a = dict(root_dir=root, dataset="synth", g_norm=G, sigma_na=0.1, sigma_ng=1e-3, sigma_nba=1e-2, sigma_nbg=1e-4,
             init_attitude_sigma=0.01, init_yaw_sigma=0.01, init_vel_sigma=0.1, init_pos_sigma=0.1, init_bg_sigma=1e-4,
             init_ba_sigma=1e-4, use_const_cov=True, const_cov_val_x=0.01, const_cov_val_y=0.01, const_cov_val_z=0.01,
             meascov_scale=1.0, mahalanobis_factor=-1.0, mahalanobis_fail_scale=0.0, log_full_state=False,
             initialize_with_gt=True, initialize_with_offline_calib=True, update_freq=20.0, save_as_npy=False,
             model_path=os.path.join(model_dir, "c.pt"), model_param_path=os.path.join(model_dir, "p.json"),
             imu_intrinsics=None)
    a.update(kw)
    return dotdict(a)


def run_oracle(s, frame, torque="none", yaw0_deg=0.0, check_features=None):
    with tempfile.TemporaryDirectory() as root:
        write_sequence(root, s)
        args = make_args(root, root, frame, torque)
        out = os.path.join(root, "res")
        os.makedirs(out)
        fm = FilterManager(args, "seq", out)
        ms = fm.runner.meas_source

        def oracle(t_s, features):
            if check_features is not None:
                check_features(t_s, features)
            i = int(round((t_s[0] - s["t"][0]) / DT))
            dp = s["p"][i + 50] - s["p"][i]
            if frame == "body":
                dp = s["R"][i].T @ dp
            return dp.reshape((3, 1)), np.eye(3)

        ms.get_displacement_measurement = oracle
        fm.run(args)
        est = np.loadtxt(os.path.join(out, "stamped_traj_estimate.txt"))
        vel = np.loadtxt(os.path.join(out, "stamped_vel_estimate.txt"))
        cov = np.loadtxt(os.path.join(out, "stamped_vel_cov_updates.txt"))
    return est, vel, cov


@pytest.mark.parametrize("frame", ["world", "body"])
def test_oracle_displacement_keeps_filter_on_truth(frame):
    s = synthetic_flight()
    est, vel, cov = run_oracle(s, frame)
    k = np.searchsorted(s["t"], est[:, 0] - 1e-6)
    assert np.sqrt(((est[:, 1:4] - s["p"][k]) ** 2).sum(1).mean()) < 0.05
    assert np.sqrt(((vel[:, 1:4] - s["v"][k]) ** 2).sum(1).mean()) < 0.1
    assert len(cov) > 300 and cov.shape[1] == 13


@pytest.mark.parametrize("frame", ["world", "body"])
def test_filter_features_match_training_features(frame):
    """The filter's window, integrated from its own attitude, must reproduce what the network was trained on."""
    s = synthetic_flight()
    seen = []
    tau = np.gradient(s["w"], DT, axis=0)

    def check(t_s, features):
        i = int(round((t_s[0] - s["t"][0]) / DT))
        ref = build_features(s["w"][i:i + 50], np.c_[np.zeros((50, 2)), s["acc"][i:i + 50, 2]], s["R"][i:i + 50],
                             tau[i:i + 50], frame, G)
        assert features.shape == (50, 9)
        seen.append(np.abs(features - ref).max())

    run_oracle(s, frame, "gyro", check_features=check)
    assert len(seen) > 300
    assert np.median(seen) < 0.05


def test_window_data_matches_filter_update_span():
    s = synthetic_flight()
    with tempfile.TemporaryDirectory() as root:
        write_sequence(root, s)
        for frame in ("world", "body"):
            d = WindowData(root, "synth", ["seq"], 50, frame=frame, torque="gyro", g=G)
            feat, targ = d.batch(np.array([100]))
            dp = s["p"][150] - s["p"][100]                                         # 50 steps, as in the filter
            np.testing.assert_allclose(targ[0], dp if frame == "world" else s["R"][100].T @ dp, atol=1e-5)
            assert feat.shape == (1, 9, 50)


def test_body_update_jacobian_is_numerically_correct():
    cfg = dotdict(g_norm=G, sigma_na=0.1, sigma_ng=1e-3, sigma_nba=1e-2, sigma_nbg=1e-4, init_attitude_sigma=0.01,
                  init_yaw_sigma=0.01, init_vel_sigma=0.1, init_pos_sigma=0.1, init_bg_sigma=1e-4, init_ba_sigma=1e-4,
                  use_const_cov=True, const_cov_val_x=0.01, const_cov_val_y=0.01, const_cov_val_z=0.01, meascov_scale=1.0,
                  mahalanobis_factor=-1.0, mahalanobis_fail_scale=0.0)
    f = ImuMSCKF(cfg)
    R0 = Rotation.from_rotvec([0.3, -0.2, 0.9]).as_matrix()
    f.initialize_with_state(0, R0, np.array([[1.0], [0.5], [0.2]]), np.array([[0.1], [-0.2], [1.0]]), np.zeros((3, 1)), np.zeros((3, 1)))
    acc, gyr = np.array([[0.5], [0.2], [10.0]]), np.array([[0.2], [-0.1], [0.4]])
    stamps = []
    for k in range(1, 6):
        t = k * 10000
        f.propagate(acc, gyr, t, t_augmentation_us=t)
        stamps.append(t)
    t0, t1 = stamps[1], stamps[-1]
    meas = np.array([[0.1], [0.0], [0.2]])
    ok, innov, H, _ = f.learnt_model_update(meas, np.eye(3), t0, t1, body_frame=True)
    assert ok
    n = H.shape[1]
    eps = 1e-6
    i, j = f.state.si_timestamps_us.index(t0), f.state.si_timestamps_us.index(t1)

    def h(dx):
        R = mat_exp(dx[9 * i:9 * i + 3].reshape(3, 1)) @ f.state.si_Rs[i]          # the convention in apply_correction
        pi = f.state.si_ps[i] + dx[9 * i + 6:9 * i + 9].reshape(3, 1)
        pj = f.state.si_ps[j] + dx[9 * j + 6:9 * j + 9].reshape(3, 1)
        return R.T @ (pj - pi)

    num = np.zeros_like(H)
    for k in range(n):
        d = np.zeros(n)
        d[k] = eps
        num[:, k] = ((h(d) - h(-d)) / (2 * eps)).ravel()
    np.testing.assert_allclose(H, num, atol=1e-6)


def test_body_features_are_invariant_to_heading_error_and_world_features_are_not():
    s = synthetic_flight()
    yaw = Rotation.from_euler("z", 20, degrees=True).as_matrix()
    th = np.c_[np.zeros((50, 2)), s["acc"][:50, 2]]
    a = build_features(s["w"][:50], th, s["R"][:50], None, "body", G)
    b = build_features(s["w"][:50], th, yaw @ s["R"][:50], None, "body", G)
    np.testing.assert_allclose(a, b, atol=1e-9)
    a = build_features(s["w"][:50], th, s["R"][:50], None, "world", G)
    b = build_features(s["w"][:50], th, yaw @ s["R"][:50], None, "world", G)
    assert np.abs(a - b).max() > 0.1


def test_world_features_match_upstream_order():
    """[R w, R T], the order the shipped Blackbird checkpoint expects."""
    w, T = np.array([[1.0, 0, 0]]), np.array([[0, 0, 5.0]])
    R = Rotation.from_euler("x", 90, degrees=True).as_matrix()[None]
    np.testing.assert_allclose(build_features(w, T, R), [[1, 0, 0, 0, -5, 0]], atol=1e-9)


def test_filter_survives_gaps_and_float_timestamps():
    """A 50 ms hole in the log (NanoBench) and times that truncate to 1 us less (8.235 s)."""
    s = synthetic_flight()
    keep = np.ones(len(s["t"]), bool)
    keep[500:504] = False
    for k in ("t", "p", "v", "R", "q", "w", "acc"):
        s[k] = s[k][keep]
    s["t"] = s["t"] + 8.235
    with tempfile.TemporaryDirectory() as root:
        write_sequence(root, s)
        args = make_args(root, root, "world")
        out = os.path.join(root, "res")
        os.makedirs(out)
        fm = FilterManager(args, "seq", out)
        fm.run(args)
        assert np.loadtxt(os.path.join(out, "stamped_vel_cov_updates.txt")).shape[0] > 200


def test_windows_spanning_a_position_jump_are_dropped():
    s = synthetic_flight()
    s["p"] = s["p"].copy()
    s["p"][700] += 2.0
    with tempfile.TemporaryDirectory() as root:
        write_sequence(root, s)
        d = WindowData(root, "synth", ["seq"], 50)
    # steps 699 and 700 are bad; window i spans steps i .. i+49
    assert d.n_dropped == 51
    assert not np.any((d.starts <= 700) & (d.starts + 50 > 699))
    assert 648 in d.starts and 701 in d.starts
