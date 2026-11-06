"""Collect the released models: per dataset and variant, the stage 1 seed with the lowest validation loss.

    python3 scripts/release/build_weights.py --out <dir>      writes <dir>/<dataset>/<variant>/ and <dir>/MODELS.md

Each folder holds what a user needs to run the model on that dataset's converted data:
    checkpoint_best.pt          weights only ({"model_state_dict", "step", "val_rmse"})
    model_net_parameters.json   frame, torque source, window; no local paths
    physics.json                the platform's thrust map and torque allocation (used to build the inputs)
    filter.json                 EKF setting tuned on validation for this dataset and variant (all seeds)
    metrics.json                validation loss, and this seed's test (and AI-IO unseen) metrics
The seed is chosen on validation only; test numbers are reported, never used to choose.
"""
import argparse
import json
import os
import shutil
import sys

import numpy as np
import pandas as pd
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "..", "src"))
from eximo_paths import REPO, RESULTS  # noqa: E402
from select_and_test import parse_setting  # noqa: E402

DATASETS = ("ai_io", "nanobench", "tii_ratm", "neurobem")
VARIANTS = {"world_none": "base IMO (world frame, no torque)", "body_gyro": "Ex-IMO, gyro-derived torque (as specified)",
            "body_rotor": "Ex-IMO, rotor-derived torque (recommended)"}
SEEDS = (42, 43, 44)
KEEP = ("dataset", "frame", "torque", "input_dim", "output_dim", "imu_freq", "sampling_freq", "window_time", "g_norm",
        "seed", "lr", "batch_size", "max_steps", "patience_steps", "sigma_ori_deg", "sigma_bg")


def per_seq_mean(csv, cols):
    if not os.path.exists(csv):
        return None
    d = pd.read_csv(csv)
    return {c: float(np.nanmean(pd.to_numeric(d[c], errors="coerce"))) for c in cols if c in d}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    rows = []
    for ds in DATASETS:
        with open(os.path.join(RESULTS, "s1", ds, "selection.json")) as f:
            sel = json.load(f)
        for v, desc in VARIANTS.items():
            best = None
            for s in SEEDS:
                md = os.path.join(RESULTS, "s1", ds, v, f"seed{s}", ds, "checkpoints", "model_net")
                ck = torch.load(os.path.join(md, "checkpoint_best.pt"), map_location="cpu", weights_only=False)
                if best is None or ck["val_rmse"] < best[1]["val_rmse"]:
                    best = (s, ck, md)
            s, ck, md = best
            dst = os.path.join(a.out, ds, v)
            os.makedirs(dst, exist_ok=True)
            torch.save({"model_state_dict": ck["model_state_dict"], "step": ck["step"], "val_rmse": ck["val_rmse"]},
                       os.path.join(dst, "checkpoint_best.pt"))
            with open(os.path.join(md, "model_net_parameters.json")) as f:
                p = json.load(f)
            with open(os.path.join(dst, "model_net_parameters.json"), "w") as f:
                json.dump({k: p[k] for k in KEEP if k in p}, f, indent=1)
            shutil.copy(os.path.join(REPO, "config", "physics", f"{ds}.json"), os.path.join(dst, "physics.json"))
            c, n, freq = parse_setting(sel["filter"][v]["setting"])
            with open(os.path.join(dst, "filter.json"), "w") as f:
                json.dump(dict(setting=sel["filter"][v]["setting"], const_cov=c, sigma_na=n[0], sigma_ng=n[1], sigma_nba=n[2],
                               sigma_nbg=n[3], update_freq=freq, chosen_on="validation, mean over seeds 42-44"), f, indent=1)
            run = os.path.join(RESULTS, "s1", ds, v, f"seed{s}")
            m = dict(variant=v, description=desc, dataset=ds, seed=s, val_displacement_rmse_m=float(ck["val_rmse"]), step=int(ck["step"]))
            for lst in ("test", "unseen"):
                f_ = per_seq_mean(os.path.join(run, f"{lst}_filter.csv"), ("vel_RMSE", "ATE_se3", "RE_T"))
                n_ = per_seq_mean(os.path.join(run, f"{lst}_net.csv"), ("RMSE", "AVE"))
                if f_:
                    m[lst] = dict(filter=f_, network=n_)
            with open(os.path.join(dst, "metrics.json"), "w") as f:
                json.dump(m, f, indent=1)
            rows.append(m)
            print(ds, v, "seed", s, f"val {ck['val_rmse']:.4f}")
    lines = ["# Released models", "", "Stage 1 models, one per dataset and variant: the seed with the lowest validation loss. "
             "Test numbers are this seed's (the README reports means over 3 seeds).", "",
             "| dataset | variant | seed | val Δp RMSE [m] | test filter vel RMSE [m/s] | test ATE_se3 [m] | test network RMSE [m/s] |",
             "|---|---|---|---|---|---|---|"]
    for m in rows:
        t = m.get("test", {})
        lines.append(f"| {m['dataset']} | {m['variant']} | {m['seed']} | {m['val_displacement_rmse_m']:.3f} | "
                     f"{t.get('filter', {}).get('vel_RMSE', float('nan')):.3f} | {t.get('filter', {}).get('ATE_se3', float('nan')):.2f} | "
                     f"{t.get('network', {}).get('RMSE', float('nan')):.3f} |")
    with open(os.path.join(a.out, "MODELS.md"), "w") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
