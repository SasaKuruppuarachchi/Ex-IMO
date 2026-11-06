"""Filter tuning on the validation split, CPU: the same grid and protocol for every model.

    python3 scripts/filter_sweep.py --dataset tii_ratm --runs r1 r2 ... --out sweep.csv --jobs 12

Each run is <results>/<run>/<dataset>/checkpoints/model_net. Runs every setting in the grid on --list and writes one row per
(run, setting) with the mean per-sequence metrics. The selection rule is in select_and_test.py.
"""
import argparse
import itertools
import os
import shutil
import subprocess
import sys
from multiprocessing import Pool

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from evaluation import metrics as M  # noqa: E402
from learning.data_management.windows import get_datalist  # noqa: E402

from eximo_paths import DATA, REPO, RESULTS  # noqa: E402

# Per-axis gyro scale fitted on NeuroBEM's training split (config/imu_intrinsics/neurobem.json).
INTRINSICS = {"neurobem": os.path.join(REPO, "config", "imu_intrinsics", "neurobem.json")}
# Stage 1 picked the largest const_cov, sigma_na and the slowest update on several variants, so the grid was extended twice
# (to 3 and 10, then to 10 and 30) before any test result was looked at. Rows already in --out are kept, not rerun.
GRID = dict(const_cov=[0.01, 0.03, 0.1, 0.3, 1.0, 3.0, 10.0],
            noise=[(0.1, 1e-3, 1e-2, 1e-4), (1.0, 1e-2, 0.1, 1e-3), (3.0, 1e-2, 0.1, 1e-3), (10.0, 1e-2, 0.1, 1e-3),
                   (30.0, 1e-2, 0.1, 1e-3)],
            update_freq=[20.0, 10.0, 5.0])


def setting_name(c, n, f):
    return f"cov{c}_na{n[0]}_ng{n[1]}_uf{int(f)}"


def filter_cmd(dataset, run, seq_list, out, const_cov, noise, freq, checkpoint):
    cmd = ["python3", "src/main_filter.py", "--root_dir", DATA, "--dataset", dataset, "--data_list", seq_list,
           "--out_dir", out, "--model_dir", os.path.join(RESULTS, run, dataset, "checkpoints", "model_net"),
           "--checkpoint_fn", checkpoint, "--g_norm", "9.81", "--cpu", "--update_freq", str(freq),
           "--const_cov_val_x", str(const_cov), "--const_cov_val_y", str(const_cov), "--const_cov_val_z", str(const_cov),
           "--sigma_na", str(noise[0]), "--sigma_ng", str(noise[1]), "--sigma_nba", str(noise[2]), "--sigma_nbg", str(noise[3])]
    base = dataset.split("__")[0]                                                  # a held-out-shape fold has its dataset's IMU
    if base in INTRINSICS:
        cmd += ["--imu_intrinsics", INTRINSICS[base]]
    return cmd


def one(job):
    dataset, run, seq_list, const_cov, noise, freq, checkpoint, tmp = job
    name = setting_name(const_cov, noise, freq)
    out = os.path.join(tmp, run.replace("/", "_"), name)
    os.makedirs(out, exist_ok=True)
    env = dict(os.environ, OMP_NUM_THREADS="1", MKL_NUM_THREADS="1", NUMBA_NUM_THREADS="1")
    p = subprocess.run(filter_cmd(dataset, run, seq_list, out, const_cov, noise, freq, checkpoint),
                       env=env, capture_output=True, text=True)
    rows = []
    for seq in get_datalist(os.path.join(DATA, dataset, seq_list)):
        d = os.path.join(out, dataset, seq, "pyfilter")
        try:
            rows.append(M.evaluate_sequence(os.path.join(DATA, dataset, seq, "stamped_groundtruth_imu.txt"),
                                            os.path.join(d, "stamped_traj_estimate.txt"),
                                            os.path.join(d, "stamped_vel_estimate.txt"),
                                            os.path.join(d, "stamped_vel_cov_updates.txt")))
        except Exception as ex:
            rows.append(dict(status=f"{type(ex).__name__}"))
    shutil.rmtree(out, ignore_errors=True)
    df = pd.DataFrame(rows)
    row = dict(run=run, setting=name, const_cov=const_cov, sigma_na=noise[0], sigma_ng=noise[1], update_freq=freq,
               returncode=p.returncode, n_failed=int((df.get("vel_RMSE", pd.Series(dtype=float)).isna()).sum() + (len(rows) - len(df))))
    for k in ("vel_RMSE", "ATE_se3", "ATE_none", "RE_T", "nees_median", "nees_in95"):
        row[k] = float(df[k].mean()) if k in df else np.nan
    return row


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--runs", nargs="+", required=True, help="relative to the results folder")
    ap.add_argument("--list", default="val.txt")
    ap.add_argument("--checkpoint", default="checkpoint_best.pt")
    ap.add_argument("--out", required=True)
    ap.add_argument("--jobs", type=int, default=12)
    a = ap.parse_args()
    tmp = os.path.join(RESULTS, "_sweep_tmp", a.dataset)
    old = pd.read_csv(a.out) if os.path.exists(a.out) else pd.DataFrame(columns=["run", "setting"])
    done = set(zip(old.run, old.setting))
    jobs = [(a.dataset, r, a.list, c, n, f, a.checkpoint, tmp)
            for r, c, n, f in itertools.product(a.runs, GRID["const_cov"], GRID["noise"], GRID["update_freq"])
            if (r, setting_name(c, n, f)) not in done]
    rows = old.to_dict("records")
    with Pool(a.jobs) as pool:
        for i, r in enumerate(pool.imap_unordered(one, jobs), 1):
            rows.append(r)
            if i % 20 == 0:
                print(f"{i}/{len(jobs)}", flush=True)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    pd.DataFrame(rows).to_csv(a.out, index=False)
    print("wrote", a.out)


if __name__ == "__main__":
    main()
