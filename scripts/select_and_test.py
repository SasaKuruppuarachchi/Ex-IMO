"""Stage evaluation on CPU: tune the filter on validation, choose the torque source on validation, then run test once.

    python3 scripts/select_and_test.py --stage s1 --dataset tii_ratm --seeds 42 43 44 --jobs 12

Rules, fixed before any trained model was evaluated:
- Filter setting, per dataset and variant: the lowest validation score, averaged over seeds. Score = mean of the ratios
  vel_RMSE, ATE_se3, RE_T to the default filter's. Settings where a sequence failed
  are excluded. The default filter is const_cov 0.01, (0.1, 1e-3, 1e-2, 1e-4), 20 Hz, as upstream.
- Torque source, per dataset: the body-frame variant with the lower mean of validation vel_RMSE, ATE_se3, RE_T ratios
  to the other one, each at its tuned filter. All variants still run on test, so the choice stays auditable.
Writes under <results>/<stage>/<dataset>/: sweep_<variant>.csv, selection.json, <variant>/seed<k>/{test,unseen}_*.csv.
"""
import argparse
import json
import os
import subprocess

import numpy as np
import pandas as pd

from filter_sweep import DATA, GRID, RESULTS, filter_cmd, setting_name

METRICS = ("vel_RMSE", "ATE_se3", "RE_T")
DEFAULT = setting_name(0.01, (0.1, 1e-3, 1e-2, 1e-4), 20.0)
VARIANTS = ("world_none", "body_gyro", "body_rotor")


def pick_setting(df):
    """df: rows of one variant across seeds. Returns the chosen row and the score table."""
    scores = []
    for setting, g in df.groupby("setting"):
        ratios = []
        ok = True
        for _, r in g.iterrows():
            base = df[(df.run == r.run) & (df.setting == DEFAULT)].iloc[0]
            if r.returncode != 0 or r.n_failed > 0:
                ok = False
            ratios.append(np.mean([r[m] / base[m] for m in METRICS]))
        if ok:
            scores.append(dict(setting=setting, score=float(np.mean(ratios)), **{m: float(g[m].mean()) for m in METRICS}))
    return pd.DataFrame(scores).sort_values("score").reset_index(drop=True)


def sh(cmd, log=None):
    env = dict(os.environ, OMP_NUM_THREADS="2", MKL_NUM_THREADS="2", NUMBA_NUM_THREADS="2")
    p = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if log:
        with open(log, "w") as f:
            f.write(p.stdout + p.stderr)
    return p.returncode


def parse_setting(name):
    for c in GRID["const_cov"]:
        for n in GRID["noise"]:
            for f in GRID["update_freq"]:
                if setting_name(c, n, f) == name:
                    return c, n, f
    raise ValueError(name)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stage", default="s1")
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--seeds", nargs="+", type=int, default=[42, 43, 44])
    ap.add_argument("--variants", nargs="+", default=list(VARIANTS))
    ap.add_argument("--jobs", type=int, default=12)
    ap.add_argument("--lists", nargs="+", default=["test", "unseen"])
    a = ap.parse_args()
    base = os.path.join(RESULTS, a.stage, a.dataset)
    chosen = {}
    tables = {}
    for v in a.variants:
        out = os.path.join(base, f"sweep_{v}.csv")
        runs = [f"{a.stage}/{a.dataset}/{v}/seed{s}" for s in a.seeds]
        subprocess.run(["python3", "scripts/filter_sweep.py", "--dataset", a.dataset, "--runs", *runs, "--out", out,  # runs only missing settings
                        "--jobs", str(a.jobs)], check=True)
        t = pick_setting(pd.read_csv(out))
        tables[v] = t
        chosen[v] = t.iloc[0].to_dict()
        print(a.dataset, v, "->", chosen[v], flush=True)
    sel = dict(dataset=a.dataset, seeds=a.seeds, filter=chosen)
    if "body_gyro" in chosen and "body_rotor" in chosen:
        ratio = np.mean([chosen["body_rotor"][m] / chosen["body_gyro"][m] for m in METRICS])
        sel["rotor_over_gyro_val"] = float(ratio)
        sel["torque_choice"] = "body_rotor" if ratio < 1 else "body_gyro"
        print(a.dataset, "torque choice on validation:", sel["torque_choice"], f"(rotor/gyro {ratio:.3f})", flush=True)
    with open(os.path.join(base, "selection.json"), "w") as f:
        json.dump(sel, f, indent=1)

    for v in a.variants:
        c, n, freq = parse_setting(chosen[v]["setting"])
        for s in a.seeds:
            run = f"{a.stage}/{a.dataset}/{v}/seed{s}"
            model_dir = os.path.join(RESULTS, run, a.dataset, "checkpoints", "model_net")
            for lst in a.lists:
                if not os.path.exists(os.path.join(DATA, a.dataset, lst + ".txt")):
                    continue
                d = os.path.join(RESULTS, run)
                res = os.path.join(d, f"res_{lst}")
                sh(filter_cmd(a.dataset, run, lst + ".txt", res, c, n, freq, "checkpoint_best.pt"), os.path.join(d, f"filter_{lst}.log"))
                sh(["python3", "scripts/eval_filter.py", "--data_root", DATA, "--dataset", a.dataset, "--res_root", res,
                    "--seq_list", os.path.join(DATA, a.dataset, lst + ".txt"), "--out", os.path.join(d, f"{lst}_filter.csv")])
                sh(["python3", "scripts/eval_net.py", "--root_dir", DATA, "--dataset", a.dataset, "--model_dir", model_dir,
                    "--list", lst + ".txt", "--out", os.path.join(d, f"{lst}_net.csv")])
    print("finished", a.dataset, flush=True)


if __name__ == "__main__":
    main()
