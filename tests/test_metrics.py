import importlib.util
import os
import subprocess
import sys

import numpy as np
import pytest
from scipy.spatial.transform import Rotation

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
from evaluation import metrics as M  # noqa: E402


def _load_script(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, "..", "scripts", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def circle(T=60.0, hz=100, r=10.0, w=0.2):
    ts = np.arange(0, T, 1.0 / hz)
    p = np.stack([r * np.cos(w * ts), r * np.sin(w * ts), 0.1 * ts], 1)
    yaw = w * ts + np.pi / 2
    q = Rotation.from_euler("z", yaw).as_quat()
    v = np.stack([-r * w * np.sin(w * ts), r * w * np.cos(w * ts), 0.1 + 0 * ts], 1)
    return dict(ts=ts, p=p, q=q, v=v)


def line(T=60.0, hz=100, speed=2.0):
    ts = np.arange(0, T, 1.0 / hz)
    p = np.stack([speed * ts, 0 * ts, 0 * ts], 1)
    q = np.tile([0, 0, 0, 1.0], (len(ts), 1))
    v = np.tile([speed, 0, 0], (len(ts), 1))
    return dict(ts=ts, p=p, q=q, v=v)


def write_gt(path, g):
    np.savetxt(path, np.c_[g["ts"], g["p"], g["q"], g["v"]], header="ts x y z qx qy qz qw vx vy vz")


def test_quaternion_convention():
    q = Rotation.from_euler("z", 90, degrees=True).as_quat()  # xyzw
    np.testing.assert_allclose(q, [0, 0, np.sqrt(0.5), np.sqrt(0.5)])
    # body->world: body x axis ends up along world y
    np.testing.assert_allclose(Rotation.from_quat(q).apply([1, 0, 0]), [0, 1, 0], atol=1e-12)


def test_align_sim3_and_se3_recovery():
    rng = np.random.default_rng(0)
    gt = rng.normal(size=(200, 3)) * 5
    R = Rotation.from_euler("zyx", [30, -20, 10], degrees=True).as_matrix()
    t = np.array([1.0, -2.0, 3.0])
    est = (gt - t) @ R / 1.0  # gt = R est + t
    s, R2, t2 = M.align_se3(est, gt)
    assert s == 1.0
    np.testing.assert_allclose(R2, R, atol=1e-9)
    np.testing.assert_allclose(t2, t, atol=1e-9)
    est_s = est / 2.5  # gt = 2.5 R est_s + t
    s, R2, t2 = M.align_sim3(est_s, gt)
    assert s == pytest.approx(2.5)
    np.testing.assert_allclose(R2, R, atol=1e-9)
    np.testing.assert_allclose(t2, t, atol=1e-9)
    a = M.ate(est_s, gt)
    assert a["ATE_sim3"] < 1e-9 and a["ATE_se3"] > 0.1 and a["ATE_none"] > 0.1
    a = M.ate(est, gt)
    assert a["ATE_se3"] < 1e-9 and a["ATE_sim3"] < 1e-9 and a["ATE_none"] > 0.1


def test_umeyama_no_reflection():
    rng = np.random.default_rng(1)
    gt = rng.normal(size=(50, 3))
    _, R, _ = M.align_sim3(gt * [1, 1, -1], gt)  # mirrored input: must still return a proper rotation
    assert np.linalg.det(R) == pytest.approx(1.0)


def test_ate_translation_offset():
    g = circle()
    a = M.ate(g["p"] + [3, 4, 0], g["p"])
    assert a["ATE_none"] == pytest.approx(5.0)
    assert a["ATE_se3"] < 1e-9


def test_yaw_rotated_estimate_has_zero_relative_error():
    g = circle()
    Rz = Rotation.from_euler("z", 40, degrees=True)
    e = dict(ts=g["ts"], p=Rz.apply(g["p"]) + [5, 5, 5], q=(Rz * Rotation.from_quat(g["q"])).as_quat())
    r = M.relative_error(e, g)
    assert r["RE_T"] < 1e-9
    assert M.ate(e["p"], g["p"])["ATE_se3"] < 1e-9
    assert M.ate(e["p"], g["p"])["ATE_none"] > 1


def test_relative_error_straight_line_drift():
    g = line(T=60, speed=2.0)  # 120 m path
    e = dict(ts=g["ts"], p=g["p"] + np.outer(g["ts"], [0, 0.1, 0]), q=g["q"])
    r = M.relative_error(e, g)
    # segment of length L lasts L/2 s -> lateral error 0.1*L/2 = 0.05 L
    assert r["RE_10pct_mean"] == pytest.approx(0.05 * 12, rel=1e-2)
    assert r["RE_10pct_pct"] == pytest.approx(5.0, rel=1e-2)
    assert r["RE_50pct_mean"] == pytest.approx(0.05 * 60, rel=1e-2)
    assert r["RE_T"] == pytest.approx(0.05 * 36, rel=1e-2)
    r = M.relative_error(e, g, lengths=[10, 20], fractional=False)
    assert r["RE_10m_mean"] == pytest.approx(0.5, rel=1e-2)
    assert r["RE_20m_rmse"] == pytest.approx(1.0, rel=1e-2)


def test_relative_error_uses_orientation_convention():
    g = circle()
    assert M.relative_error(g, g)["RE_T"] < 1e-9
    wrong = dict(g)
    wrong["q"] = np.tile([0, 0, 0, 1.0], (len(g["ts"]), 1))  # same positions, ignores heading
    assert M.relative_error(wrong, g)["RE_T"] > 1.0


def test_too_short_sequence_nan_not_raise():
    g = line(T=2.0, speed=1.0)  # 2 m path
    r = M.relative_error(g, g, lengths=[10, 20], fractional=False)
    assert np.isnan(r["RE_10m_mean"]) and np.isnan(r["RE_T"]) and r["RE_20m_n"] == 0
    r = M.relative_error(g, g)  # fractional lengths still work
    assert r["RE_T"] == pytest.approx(0.0, abs=1e-9)
    r = M.aiio_metrics(g["p"], g["p"])
    assert np.isnan(r["RTE_aiio"]) and r["ATE_aiio"] == 0


def test_velocity_errors_and_aiio():
    g = line(speed=2.0)
    b = np.array([0.3, 0.4, 0.0])
    r = M.velocity_errors(g["v"] + b, g["v"])
    assert r["vel_RMSE"] == pytest.approx(0.5) and r["vel_mean"] == pytest.approx(0.5)
    v = np.random.default_rng(0).normal(size=(100, 3))
    r = M.velocity_errors(v, 0 * v)
    assert r["vel_RMSE"] > r["vel_mean"]  # RMSE >= mean (Jensen)
    # aiio: constant velocity bias 0.1 m/s along y, 100 Hz -> drift over 499 samples = 0.1*4.99
    e = g["p"] + np.outer(g["ts"], [0, 0.1, 0])
    a = M.aiio_metrics(e, g["p"])
    assert a["RTE_aiio"] == pytest.approx(0.499, rel=1e-6)
    assert a["ATE_aiio"] == pytest.approx(M.ate(e, g["p"])["ATE_none"])


def test_nees_known_covariance(tmp_path):
    g = line()
    err = np.array([1.0, 2.0, 3.0])
    S = np.diag([1.0, 4.0, 9.0])  # nees = 1 + 1 + 1 = 3
    ts = np.linspace(1, 50, 20)
    v = np.tile(g["v"][0] + err, (20, 1))
    r = M.nees(ts, v, np.tile(S, (20, 1, 1)), g)
    assert r["nees_median"] == pytest.approx(3.0)
    assert r["nees_in95"] == 1.0 and r["nees_over95"] == 0.0 and r["nees_under95"] == 0.0
    r = M.nees(ts, v, np.tile(S / 100, (20, 1, 1)), g)  # nees = 300
    assert r["nees_over95"] == 1.0
    r = M.nees(ts, v, np.tile(S * 100, (20, 1, 1)), g)  # nees = 0.03
    assert r["nees_under95"] == 1.0
    # updates outside GT range are dropped
    ts2 = np.r_[ts, 1000.0]
    r = M.nees(ts2, np.r_[v, v[:1]], np.tile(S, (21, 1, 1)), g)
    assert r["nees_median"] == pytest.approx(3.0)


def test_match_traj_drops_outside_range():
    g = line(T=10)
    est = dict(ts=np.array([-1.0, 0.5, 5.0, 9.9, 20.0]), p=np.zeros((5, 3)), q=np.tile([0, 0, 0, 1.0], (5, 1)))
    e, gi = M.match_traj(est, g)
    np.testing.assert_allclose(e["ts"], [0.5, 5.0, 9.9])
    np.testing.assert_allclose(gi["p"][:, 0], 2 * e["ts"], atol=1e-9)
    assert Rotation.from_quat(gi["q"]).magnitude().max() < 1e-9


def test_evaluate_sequence_files(tmp_path):
    g = circle(T=30)
    gp = tmp_path / "gt.txt"
    write_gt(gp, g)
    ts = g["ts"][5:-5]
    np.savetxt(tmp_path / "traj.txt", np.c_[ts, g["p"][5:-5] + [1, 0, 0], g["q"][5:-5]])
    np.savetxt(tmp_path / "vel.txt", np.c_[ts, g["v"][5:-5] + [0, 0.5, 0]])
    nv = np.c_[ts[::10], g["v"][5:-5][::10], np.tile(np.eye(3).ravel() * 0.25, (len(ts[::10]), 1))]
    np.savetxt(tmp_path / "upd.txt", nv)
    r = M.evaluate_sequence(str(gp), str(tmp_path / "traj.txt"), str(tmp_path / "vel.txt"), str(tmp_path / "upd.txt"))
    assert r["ATE_none"] == pytest.approx(1.0, rel=1e-3)
    assert r["vel_RMSE"] == pytest.approx(0.5, rel=1e-3)
    assert r["RE_T"] == pytest.approx(0.0, abs=1e-6)
    assert r["nees_median"] == pytest.approx(0.0, abs=1e-6)  # est vel == gt vel at updates


def _write_csvs(tmp_path, model, scale, n_seeds=4, n_seq=12, nan_seq=None, noise=0.05):
    rng = np.random.default_rng(7)
    base = np.linspace(1, 2, n_seq)
    specs = []
    for s in range(n_seeds):
        import pandas as pd
        vals = base * scale * (1 + noise * rng.normal(size=n_seq))
        if nan_seq is not None:
            vals[nan_seq] = np.nan
        p = tmp_path / f"{model}_{s}.csv"
        pd.DataFrame(dict(sequence=[f"s{i}/x" for i in range(n_seq)], status="ok", ATE_se3=vals)).to_csv(p, index=False)
        specs.append(f"{model}:{s}:{p}")
    return specs


def test_compare_models(tmp_path):
    cm = _load_script("compare_models")
    specs = _write_csvs(tmp_path, "base", 1.0) + _write_csvs(tmp_path, "new", 0.8, nan_seq=3)
    rows = cm.compare(cm.load_runs(specs), "base", ["ATE_se3"])
    r = {x["model"]: x for x in rows}["new"]
    assert -30 < r["pct_change"] < -10  # about -20 % (dropped sequence shifts the mean slightly)
    assert r["dropped"] == 1 and r["n_w"] == 11 and r["n_t"] == 4
    assert 0 <= r["t_p"] < 0.05 and 0 <= r["w_p"] < 0.05
    assert r["warn"] == ""
    # same-distribution model: positive change sign flips, p not tiny-by-construction
    specs = _write_csvs(tmp_path, "base", 1.0) + _write_csvs(tmp_path, "worse", 1.3)
    r = {x["model"]: x for x in cm.compare(cm.load_runs(specs), "base", ["ATE_se3"])}["worse"]
    assert r["pct_change"] > 0
    # few seeds -> warning
    specs = _write_csvs(tmp_path, "base", 1.0, n_seeds=2) + _write_csvs(tmp_path, "new", 0.8, n_seeds=2)
    r = {x["model"]: x for x in cm.compare(cm.load_runs(specs), "base", ["ATE_se3"])}["new"]
    assert "n_seeds<3" in r["warn"]


def test_compare_models_cli(tmp_path):
    specs = _write_csvs(tmp_path, "base", 1.0) + _write_csvs(tmp_path, "new", 0.8)
    cmd = [sys.executable, os.path.join(HERE, "..", "scripts", "compare_models.py"), "--baseline", "base",
           "--metrics", "ATE_se3", "--out", str(tmp_path / "o.md")]
    for s in specs:
        cmd += ["--csv", s]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    assert "Wilcoxon" in out and (tmp_path / "o.md").exists()


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
