"""
Network input features, shared by training and the filter so that the two can't diverge.

    world (IMO):     [R w, R T, (R tau)],        output: displacement in the world frame
    body  (Ex-IMO):  [w, T + R^T g_w, (tau)],    output: displacement in the body frame at the window's start

All inputs are per-sample. In the world frame the whole attitude, heading included, enters every channel. In the
body frame the attitude enters only through gravity, so a heading error doesn't reach the features.
"""
import numpy as np


def build_features(gyro, thrust, R, tau=None, frame="world", g=9.81):
    """gyro, thrust, tau: (..., 3). R: (..., 3, 3), body to world. Returns (..., 6 or 9)."""
    if frame == "world":
        parts = [np.einsum("...ij,...j->...i", R, x) for x in (gyro, thrust)]
        if tau is not None:
            parts.append(np.einsum("...ij,...j->...i", R, tau))
    elif frame == "body":
        g_body = np.einsum("...ji,j->...i", R, np.array([0.0, 0.0, -g]))           # R^T g_w
        parts = [gyro, thrust + g_body]
        if tau is not None:
            parts.append(tau)
    else:
        raise ValueError(f"unknown frame {frame}")
    return np.concatenate(parts, axis=-1)


def input_dim(torque):
    return 6 if torque == "none" else 9


def torque_key(torque):
    return None if torque == "none" else f"tau_{torque}"
