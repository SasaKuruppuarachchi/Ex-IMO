"""Are features and targets physically consistent? Integrate the features with the TRUE initial velocity and attitude and
compare with the target, in both frames. This needs no network: a large residual means a frame or sign bug in
features.py or windows.py, while equal residuals in the two frames mean the thrust model limits both alike.

    dp_world = v_i T + sum_k sum_{l<=k} (R_l T_l + g_w) dt^2
    dp_body  = R_i^T v_i T + sum_k sum_{l<=k} R_i^T R_l (T_l + R_l^T g_w) dt^2
"""
import argparse
import os

import h5py
import numpy as np

from eximo_paths import DATA
from learning.data_management.features import build_features
from learning.data_management.windows import WindowData, get_datalist

ap = argparse.ArgumentParser()
ap.add_argument("--root_dir", default=DATA)
ap.add_argument("--dataset", default="tii_ratm")
ap.add_argument("--list", default="val.txt")
a = ap.parse_args()
W, dt, G = 50, 0.01, 9.81
names = get_datalist(os.path.join(a.root_dir, a.dataset, a.list))
res = {}
for frame in ("world", "body"):
    d = WindowData(a.root_dir, a.dataset, names, W, frame=frame, stride=5, g=G)
    v = []
    for n in names:
        with h5py.File(os.path.join(a.root_dir, a.dataset, n, "data.hdf5"), "r") as f:
            v.append(f["traj_target_v"][()])
    v = np.concatenate(v)
    idx = np.arange(len(d))
    feat, targ = d.batch(idx)
    feat = feat.transpose(0, 2, 1)                                                 # B, W, 6
    s = d.starts
    win = s[:, None] + np.arange(W)
    if frame == "world":
        acc = feat[:, :, 3:6] + np.array([0.0, 0.0, -G])                           # R T + g_w
        v0 = v[s]
    else:
        # a_b is in the body frame of its own sample: rotate into the window's start frame
        R_rel = np.einsum("nji,ntjk->ntik", d.R[s], d.R[win])
        acc = np.einsum("ntij,ntj->nti", R_rel, feat[:, :, 3:6])
        v0 = np.einsum("nji,nj->ni", d.R[s], v[s])
    vel = v0[:, None] + np.cumsum(acc, axis=1) * dt
    dp = v0 * 0 + (np.concatenate([v0[:, None], vel[:, :-1]], axis=1) + 0.5 * acc * dt).sum(axis=1) * dt
    e = np.linalg.norm(dp - targ, axis=1)
    no_v = np.linalg.norm(targ - v0 * W * dt, axis=1)
    res[frame] = np.sqrt((e ** 2).mean())
    print(f"{a.dataset} {frame:5s}: physics residual RMSE {res[frame]:.4f} m; target norm RMS {np.sqrt((np.linalg.norm(targ, axis=1) ** 2).mean()):.3f} m; "
          f"|dp - v0 T| RMS {np.sqrt((no_v ** 2).mean()):.3f} m, {len(e)} windows")
print(f"body/world residual ratio {res['body'] / res['world']:.3f}")
