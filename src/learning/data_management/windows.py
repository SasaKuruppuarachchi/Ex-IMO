"""
In-memory sliding windows with vectorised batches. Same sampling as datasets.ModelDataset but with no per-sample
Python, plus the Ex-IMO frame and torque options.

A window starting at i uses inputs i .. i+W-1 and the target p[i+W] - p[i], which spans W steps, as the filter's
update does. Upstream's target stops one step short (W-1 steps), a 2% scale error at the filter; see docs/EX_IMO.md.

Windows spanning a sample whose position disagrees with the logged velocity are dropped: the target comes from position, and
AI-IO's manual/high/seq_4/train has motion-capture jumps of up to 2 m (scripts/diag/position_glitches.py). No other dataset
has any, so they are unaffected.
"""
import os

import h5py
import numpy as np
from scipy.spatial.transform import Rotation

from learning.data_management.features import build_features, torque_key


MAX_VEL_MISMATCH = 5.0                                                             # m/s, between dp/dt and the logged velocity


def get_datalist(list_path):
    with open(list_path) as f:
        return [s.strip() for s in f.readlines() if len(s.strip()) > 0 and not s.startswith("#")]


def random_rotations(rng, n, sigma_rad):
    """Random axis, angle ~ N(0, sigma^2)."""
    axis = rng.normal(size=(n, 3))
    axis /= np.linalg.norm(axis, axis=1, keepdims=True)
    return Rotation.from_rotvec(axis * rng.normal(scale=sigma_rad, size=(n, 1))).as_matrix()


class WindowData:
    def __init__(self, root_dir, dataset, seq_names, window, frame="world", torque="none", stride=1, g=9.81,
                 sigma_ori_deg=2.0, sigma_bg=0.005):
        self.window, self.frame, self.torque, self.g = window, frame, torque, g
        self.sigma_ori = np.deg2rad(sigma_ori_deg)
        self.sigma_bg = sigma_bg
        key = torque_key(torque)
        gyro, thrust, tau, R, p, starts, seq_ids = [], [], [], [], [], [], []
        offset = 0
        for k, name in enumerate(seq_names):
            with h5py.File(os.path.join(root_dir, dataset, name, "data.hdf5"), "r") as f:
                gyro.append(f["gyro_calib"][()])
                thrust.append(f["i_thrust"][()])
                traj = f["traj_target"][()]
                ts = f["ts"][()]
                vel = f["traj_target_v"][()] if "traj_target_v" in f else None
                if key:
                    tau.append(f[key][()])
            R.append(Rotation.from_quat(traj[:, 3:7]).as_matrix())
            p.append(traj[:, :3])
            n = len(traj)
            s = np.arange(0, n - window, stride)                                   # the target needs sample i + window
            if vel is not None:
                bad = np.linalg.norm(np.diff(traj[:, :3], axis=0) / np.diff(ts)[:, None] - vel[:-1], axis=1) > MAX_VEL_MISMATCH
                count = np.r_[0, np.cumsum(bad)]
                self.n_dropped = getattr(self, "n_dropped", 0) + int((count[s + window] != count[s]).sum())
                s = s[count[s + window] == count[s]]
            starts.append(s + offset)
            seq_ids.append(np.full(len(s), k))
            offset += n
        self.names = list(seq_names)
        self.gyro, self.thrust = np.concatenate(gyro), np.concatenate(thrust)
        self.tau = np.concatenate(tau) if key else None
        self.R, self.p = np.concatenate(R), np.concatenate(p)
        self.starts, self.seq_ids = np.concatenate(starts), np.concatenate(seq_ids)

    def __len__(self):
        return len(self.starts)

    def batch(self, idx, rng=None):
        """feat (B, C, W) and target (B, 3), float32. rng != None adds the training perturbations."""
        s = self.starts[idx]
        win = s[:, None] + np.arange(self.window)
        gyro, R = self.gyro[win], self.R[win]
        if rng is not None:
            gyro = gyro + rng.normal(scale=self.sigma_bg, size=(len(s), 1, 3))
            R = random_rotations(rng, len(s), self.sigma_ori)[:, None] @ R
        tau = None if self.tau is None else self.tau[win]
        feat = build_features(gyro, self.thrust[win], R, tau, self.frame, self.g)
        # the target is always in the true frame, whatever attitude error was simulated for the input
        dp = self.p[s + self.window] - self.p[s]
        if self.frame == "body":
            dp = np.einsum("nji,nj->ni", self.R[s], dp)                            # R_i^T dp
        return feat.transpose(0, 2, 1).astype(np.float32), dp.astype(np.float32)
