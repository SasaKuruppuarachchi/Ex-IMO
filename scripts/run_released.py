"""Run a released model (see scripts/release/build_weights.py) on converted data: EKF with its tuned setting, then metrics.

    python3 scripts/run_released.py --model <weights>/tii_ratm/body_rotor --dataset tii_ratm --list test --out <dir>

Writes <out>/<list>_filter.csv (vel_RMSE, ATE, RE_T, NEES per sequence) and <out>/<list>_net.csv (network alone), and
prints the means. The data must come from data_prep/ and the converter (README), which refit the same thrust and torque
maps (they're deterministic); physics.json in the model folder is the fit the model was trained with, to check against.
"""
import argparse
import json
import os
import subprocess
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
from eximo_paths import DATA, REPO  # noqa: E402

INTRINSICS = {"neurobem": os.path.join(REPO, "config", "imu_intrinsics", "neurobem.json")}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True, help="a released model folder")
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--list", default="test", help="test, val, unseen (AI-IO) ...")
    ap.add_argument("--data_root", default=DATA)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    with open(os.path.join(a.model, "filter.json")) as f:
        s = json.load(f)
    os.makedirs(a.out, exist_ok=True)
    seq_list = os.path.join(a.data_root, a.dataset, a.list + ".txt")
    res = os.path.join(a.out, "res_" + a.list)
    cmd = [sys.executable, os.path.join(REPO, "src", "main_filter.py"), "--root_dir", a.data_root, "--dataset", a.dataset,
           "--data_list", a.list + ".txt", "--out_dir", res, "--model_dir", a.model, "--checkpoint_fn", "checkpoint_best.pt",
           "--g_norm", "9.81", "--cpu", "--update_freq", str(s["update_freq"]),
           "--sigma_na", str(s["sigma_na"]), "--sigma_ng", str(s["sigma_ng"]), "--sigma_nba", str(s["sigma_nba"]),
           "--sigma_nbg", str(s["sigma_nbg"])]
    for ax in "xyz":
        cmd += [f"--const_cov_val_{ax}", str(s["const_cov"])]
    base = a.dataset.split("__")[0]
    if base in INTRINSICS:
        cmd += ["--imu_intrinsics", INTRINSICS[base]]
    subprocess.run(cmd, check=True, cwd=REPO)
    fcsv, ncsv = os.path.join(a.out, f"{a.list}_filter.csv"), os.path.join(a.out, f"{a.list}_net.csv")
    subprocess.run([sys.executable, os.path.join(REPO, "scripts", "eval_filter.py"), "--data_root", a.data_root, "--dataset", a.dataset,
                    "--res_root", res, "--seq_list", seq_list, "--out", fcsv], check=True, cwd=REPO)
    subprocess.run([sys.executable, os.path.join(REPO, "scripts", "eval_net.py"), "--root_dir", a.data_root, "--dataset", a.dataset,
                    "--model_dir", a.model, "--list", a.list + ".txt", "--out", ncsv], check=True, cwd=REPO)
    fm = pd.read_csv(fcsv)[["vel_RMSE", "ATE_se3", "RE_T"]].apply(pd.to_numeric, errors="coerce").mean()
    nm = pd.read_csv(ncsv)["RMSE"].mean()
    print(f"{a.dataset} {a.list}: filter vel_RMSE {fm.vel_RMSE:.3f} m/s, ATE_se3 {fm.ATE_se3:.3f} m, RE_T {fm.RE_T:.3f}; "
          f"network RMSE {nm:.3f} m/s (means over sequences)")


if __name__ == "__main__":
    main()
