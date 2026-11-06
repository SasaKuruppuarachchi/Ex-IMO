"""
Trajectory / velocity / uncertainty metrics for inertial odometry.

Conventions: positions in metres, world frame; quaternions are xyzw and
rotate body -> world (R = Rotation.from_quat(q).as_matrix(), p_world = R p_body + t).
Trajectories are dicts with keys 'ts' (N,), 'p' (N,3), 'q' (N,4), 'v' (N,3);
entries not available in a file are absent.
"""

import os

import numpy as np
from scipy.interpolate import interp1d
from scipy.spatial.transform import Rotation, Slerp

CHI2_3 = dict(median=2.366, lo=0.216, hi=9.348)
AIIO_REL_LAG = 499  # samples; matches est[500-1:] - est[:-500+1] in AI-IO's error analysis
DEFAULT_FRACTIONS = (0.1, 0.2, 0.3, 0.4, 0.5)


# ----------------------------------------------------------------------------
# I/O and interpolation
# ----------------------------------------------------------------------------
def load_gt(path):
    """Load stamped_groundtruth_imu.txt (ts x y z qx qy qz qw vx vy vz)."""
    a = np.loadtxt(path, ndmin=2)
    return dict(ts=a[:, 0], p=a[:, 1:4], q=a[:, 4:8], v=a[:, 8:11])


def load_est(traj_path, vel_path=None):
    """Load stamped_traj_estimate.txt (ts x y z qx qy qz qw) and optionally
    stamped_vel_estimate.txt (ts vx vy vz). With vel_path, 'v' is attached on
    the velocity file's own timestamps as 'ts_v' / 'v'."""
    a = np.loadtxt(traj_path, ndmin=2)
    est = dict(ts=a[:, 0], p=a[:, 1:4], q=a[:, 4:8])
    if vel_path is not None:
        b = np.loadtxt(vel_path, ndmin=2)
        est["ts_v"] = b[:, 0]
        est["v"] = b[:, 1:4]
    return est


def load_updates(path):
    """Load stamped_vel_cov_updates.txt -> ts (N,), v (N,3), S (N,3,3) (row-major)."""
    u = np.loadtxt(path, ndmin=2)
    return u[:, 0], u[:, 1:4], u[:, 4:13].reshape(-1, 3, 3)


def in_range(ts, gt_ts):
    """Boolean mask of ts inside [gt_ts[0], gt_ts[-1]]."""
    return (ts >= gt_ts[0]) & (ts <= gt_ts[-1])


def interp_gt(gt, ts):
    """GT p, v (linear) and q (Slerp) at times ts (must lie inside the GT range)."""
    p = interp1d(gt["ts"], gt["p"], axis=0)(ts)
    v = interp1d(gt["ts"], gt["v"], axis=0)(ts)
    q = Slerp(gt["ts"], Rotation.from_quat(gt["q"]))(ts).as_quat()
    return dict(ts=np.asarray(ts), p=p, q=q, v=v)


def match_traj(est, gt):
    """Drop est samples outside the GT time range and interpolate GT onto the
    rest. Returns (est_kept, gt_interp) with equal length."""
    m = in_range(est["ts"], gt["ts"])
    e = dict(ts=est["ts"][m], p=est["p"][m], q=est["q"][m])
    return e, interp_gt(gt, e["ts"])


# ----------------------------------------------------------------------------
# Alignment
# ----------------------------------------------------------------------------
def _umeyama(est, gt, with_scale):
    n = len(est)
    mu_e, mu_g = est.mean(0), gt.mean(0)
    ec, gc = est - mu_e, gt - mu_g
    cov = gc.T @ ec / n
    U, D, Vt = np.linalg.svd(cov)
    S = np.eye(3)
    if np.linalg.det(U) * np.linalg.det(Vt) < 0:
        S[2, 2] = -1.0
    R = U @ S @ Vt
    var_e = (ec ** 2).sum() / n
    s = float(np.trace(np.diag(D) @ S) / var_e) if with_scale and var_e > 0 else 1.0
    t = mu_g - s * R @ mu_e
    return s, R, t


def align_se3(est, gt):
    """Umeyama rigid alignment of est (N,3) onto gt (N,3): minimises
    sum ||gt_i - (R est_i + t)||^2. Returns (s=1.0, R, t)."""
    return _umeyama(est, gt, False)


def align_sim3(est, gt):
    """Umeyama similarity alignment: minimises sum ||gt_i - (s R est_i + t)||^2,
    s = tr(D S) / var(est), R = U S V^T from SVD of cov(gt, est). Returns (s, R, t)."""
    return _umeyama(est, gt, True)


def apply_align(p, s, R, t):
    """p' = s R p + t for p of shape (N,3)."""
    return s * p @ R.T + t


# ----------------------------------------------------------------------------
# Absolute / relative trajectory error
# ----------------------------------------------------------------------------
def _rmse_norm(d):
    return float(np.sqrt(np.mean(np.sum(d ** 2, axis=1))))


def ate(p_est, p_gt):
    """ATE_T = sqrt(1/M sum_i ||p_gt_i - p_est'_i||^2) with p_est' the estimate
    after no alignment / SE3 / Sim3 (Umeyama over the whole trajectory).
    Returns dict ATE_none, ATE_se3, ATE_sim3."""
    out = dict(ATE_none=_rmse_norm(p_gt - p_est))
    s, R, t = align_se3(p_est, p_gt)
    out["ATE_se3"] = _rmse_norm(p_gt - apply_align(p_est, s, R, t))
    s, R, t = align_sim3(p_est, p_gt)
    out["ATE_sim3"] = _rmse_norm(p_gt - apply_align(p_est, s, R, t))
    return out


def _len_name(L, frac):
    return f"{int(round(L * 100))}pct" if frac else f"{L:g}m"


def relative_error(est, gt, lengths=DEFAULT_FRACTIONS, fractional=True, step=0.5):
    """Relative error over sub-trajectories (rpg_trajectory_evaluation style).

    est, gt: matched dicts (same timestamps) with 'ts','p','q'. No alignment.
    For each length L (fraction of total GT path length if fractional, else
    metres) and start sample i every `step` seconds, the end sample j is the
    first with cumdist_gt[j] >= cumdist_gt[i] + L. With T_rel = inv(T_i) T_j,
    err = translation part of inv(T_gt_rel) T_est_rel
        = R_gt_rel^T (p_est_rel - p_gt_rel).
    Per length: RE_<name>_mean = mean ||err||, RE_<name>_rmse = sqrt(mean ||err||^2)
    [m], RE_<name>_pct = 100 * mean / L, RE_<name>_n = number of sub-trajectories.
    RE_T = mean over lengths of RE_<name>_mean (metres); RE_T_pct likewise for
    the percentages. Lengths with no valid sub-trajectory (sequence too short)
    give NaN and are ignored by RE_T (NaN if none are valid)."""
    ts = gt["ts"]
    d = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(gt["p"], axis=0), axis=1))])
    total = d[-1]
    Rg = Rotation.from_quat(gt["q"]).as_matrix()
    Re = Rotation.from_quat(est["q"]).as_matrix()
    starts = np.unique(np.searchsorted(ts, np.arange(ts[0], ts[-1], step)))
    out, means, pcts = {}, [], []
    for Lspec in lengths:
        L = Lspec * total if fractional else float(Lspec)
        name = _len_name(Lspec, fractional)
        errs = []
        if L > 0:
            for i in starts:
                j = np.searchsorted(d, d[i] + L - 1e-9)
                if j >= len(d):
                    continue
                Rgr = Rg[i].T @ Rg[j]
                pg = Rg[i].T @ (gt["p"][j] - gt["p"][i])
                pe = Re[i].T @ (est["p"][j] - est["p"][i])
                errs.append(np.linalg.norm(Rgr.T @ (pe - pg)))
        if errs:
            e = np.array(errs)
            m = float(e.mean())
            out[f"RE_{name}_mean"], out[f"RE_{name}_rmse"] = m, float(np.sqrt((e ** 2).mean()))
            out[f"RE_{name}_pct"], out[f"RE_{name}_n"] = 100 * m / L, len(e)
            means.append(m)
            pcts.append(100 * m / L)
        else:
            out[f"RE_{name}_mean"] = out[f"RE_{name}_rmse"] = out[f"RE_{name}_pct"] = np.nan
            out[f"RE_{name}_n"] = 0
    out["RE_T"] = float(np.mean(means)) if means else np.nan
    out["RE_T_pct"] = float(np.mean(pcts)) if pcts else np.nan
    return out


# ----------------------------------------------------------------------------
# Velocity and AI-IO-compatible metrics
# ----------------------------------------------------------------------------
def velocity_errors(v_est, v_gt):
    """World-frame velocity errors, e_i = v_est_i - v_gt_i:
    vel_RMSE = sqrt(mean ||e_i||^2), vel_mean = mean ||e_i||."""
    n = np.linalg.norm(v_est - v_gt, axis=1)
    return dict(vel_RMSE=float(np.sqrt(np.mean(n ** 2))), vel_mean=float(np.mean(n)))


def aiio_metrics(p_est, p_gt, lag=AIIO_REL_LAG):
    """Re-implementation of AI-IO's compute_position_velocity_orientation_errors.
    ATE_aiio = position_rmse[-1] = sqrt(mean ||p_est - p_gt||^2)   (no alignment).
    RTE_aiio = position_rrmse[-1] = sqrt(mean ||dp_est - dp_gt||^2) with
    dp = p[k+lag] - p[k] over *sample indices* (lag = 499 samples, not seconds),
    no alignment, no rotation into a local frame. NaN if fewer than lag+1 samples."""
    out = dict(ATE_aiio=_rmse_norm(p_est - p_gt))
    if len(p_est) > lag:
        out["RTE_aiio"] = _rmse_norm((p_est[lag:] - p_est[:-lag]) - (p_gt[lag:] - p_gt[:-lag]))
    else:
        out["RTE_aiio"] = np.nan
    return out


def nees(ts, v_est, S, gt):
    """Per-update world-velocity NEES, nees_k = e_k^T S_k^{-1} e_k with
    e_k = v_est_k - v_gt(ts_k) (the usual velocity NEES;
    updates outside the GT range are dropped). Against chi2(3):
    median (ideal 2.366), in95 = fraction within [0.216, 9.348], over95 = fraction
    above 9.348 (overconfident), under95 = fraction below 0.216 (underconfident).
    Returns dict nees_median, nees_in95, nees_over95, nees_under95."""
    m = in_range(ts, gt["ts"])
    if not m.any():
        return dict(nees_median=np.nan, nees_in95=np.nan, nees_over95=np.nan, nees_under95=np.nan)
    err = v_est[m] - interp1d(gt["ts"], gt["v"], axis=0)(ts[m])
    x = np.einsum("ni,ni->n", err, np.linalg.solve(S[m], err[..., None])[..., 0])
    return dict(nees_median=float(np.median(x)),
                nees_in95=float(np.mean((x >= CHI2_3["lo"]) & (x <= CHI2_3["hi"]))),
                nees_over95=float(np.mean(x > CHI2_3["hi"])),
                nees_under95=float(np.mean(x < CHI2_3["lo"])))


# ----------------------------------------------------------------------------
# Whole sequence
# ----------------------------------------------------------------------------
def evaluate_sequence(gt_path, traj_path, vel_path=None, upd_path=None, **re_kwargs):
    """All metrics for one sequence; vel/NEES parts are skipped (absent keys)
    when their files are None."""
    gt = load_gt(gt_path)
    est = load_est(traj_path, vel_path)
    e, g = match_traj(est, gt)
    if len(e["ts"]) < 2:
        raise ValueError("estimate has fewer than 2 samples inside the GT time range")
    out = dict(n_samples=len(e["ts"]))
    out.update(ate(e["p"], g["p"]))
    out.update(relative_error(e, g, **re_kwargs))
    out.update(aiio_metrics(e["p"], g["p"]))
    if vel_path is not None:
        m = in_range(est["ts_v"], gt["ts"])
        out.update(velocity_errors(est["v"][m], interp_gt(gt, est["ts_v"][m])["v"]))
    if upd_path is not None and os.path.exists(upd_path):
        ts, v, S = load_updates(upd_path)
        out.update(nees(ts, v, S, gt))
    return out
