"""Evaluate filter outputs: one CSV row per sequence, mean printed at the end."""

import argparse
import logging
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from evaluation.metrics import evaluate_sequence  # noqa: E402


def read_seq_list(path):
    with open(path) as f:
        return [l.strip() for l in f if l.strip() and not l.strip().startswith("#")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data_root", required=True)
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--res_root", required=True)
    ap.add_argument("--seq_list", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    rows = []
    for seq in read_seq_list(args.seq_list):
        gt = os.path.join(args.data_root, args.dataset, seq, "stamped_groundtruth_imu.txt")
        d = os.path.join(args.res_root, args.dataset, seq, "pyfilter")
        traj = os.path.join(d, "stamped_traj_estimate.txt")
        vel = os.path.join(d, "stamped_vel_estimate.txt")
        upd = os.path.join(d, "stamped_vel_cov_updates.txt")
        row = dict(sequence=seq)
        missing = [p for p in (gt, traj, vel) if not os.path.exists(p)]
        if missing:
            logging.warning("%s: missing %s", seq, missing)
            row["status"] = "missing: " + ",".join(os.path.basename(p) for p in missing)
        else:
            try:
                row.update(evaluate_sequence(gt, traj, vel, upd))
                row["status"] = "ok" if os.path.exists(upd) else "ok_no_cov_updates"
            except Exception as e:  # keep going on bad sequences
                logging.warning("%s: failed: %r", seq, e)
                row["status"] = f"error: {e!r}"
        rows.append(row)

    df = pd.DataFrame(rows)
    cols = ["sequence", "status"] + [c for c in df.columns if c not in ("sequence", "status")]
    df = df[cols]
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    df.to_csv(args.out, index=False)
    num = df.drop(columns=["sequence", "status"]).apply(pd.to_numeric, errors="coerce")
    print(df.to_string(index=False))
    print(f"\nmean over {int((df['status'].str.startswith('ok')).sum())}/{len(df)} sequences:")
    print(num.mean().to_string())
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
