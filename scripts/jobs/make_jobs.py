"""Write the job files for stages 1-3, one line per run, in the format of scripts/run_queue.sh, to <EXIMO_OUT>/jobs/.

    python3 scripts/jobs/make_jobs.py s1              base IMO and Ex-IMO with both torque sources, four datasets
    python3 scripts/jobs/make_jobs.py s2              attribution variants on the stage 1 datasets
    python3 scripts/jobs/make_jobs.py s3              base IMO and Ex-IMO on the held-out-shape folds

Stage 3's Ex-IMO uses, per dataset, the torque source stage 1 chose on validation (results/s1/<dataset>/selection.json),
so a dataset is skipped until stage 1 has selected it. Rerun when it has: the queue skips finished runs.
--torque tii_ratm=rotor overrides that, for a dry run only.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "src"))
from eximo_paths import DATA, OUT, RESULTS  # noqa: E402

SEEDS = (42, 43, 44)
S1_DATASETS = ("tii_ratm", "ai_io", "nanobench", "neurobem")
S1_VARIANTS = (("world", "none"), ("body", "gyro"), ("body", "rotor"))
S2_VARIANTS = (("world", "gyro"), ("world", "rotor"), ("body", "none"))
FOLDS = {"tii_ratm": ("ellipse", "lemniscate", "trackRATM"), "nanobench": ("crossing", "round"), "neurobem": ("circles", "lemniscate_cpc")}


def line(stage, dataset, frame, torque, seed):
    d = f"{RESULTS}/{stage}/{dataset}/{frame}_{torque}/seed{seed}"
    return f"{d}.log --root_dir {DATA} --dataset {dataset} --frame {frame} --torque {torque} --seed {seed} --out_dir {d}\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stage", choices=("s1", "s2", "s3"))
    ap.add_argument("--torque", nargs="*", default=[], help="dataset=gyro|rotor")
    ap.add_argument("--out")
    a = ap.parse_args()
    jobs = []
    if a.stage in ("s1", "s2"):
        variants = S1_VARIANTS if a.stage == "s1" else S2_VARIANTS
        jobs = [line(a.stage, ds, f, t, s) for s in SEEDS for ds in S1_DATASETS for f, t in variants]
    else:
        given = dict(x.split("=") for x in a.torque)
        for s in SEEDS:
            for ds, folds in FOLDS.items():
                sel = f"{RESULTS}/s1/{ds}/selection.json"
                if ds in given:
                    torque = given[ds]
                elif os.path.exists(sel):
                    with open(sel) as f:
                        torque = json.load(f)["torque_choice"].split("_")[1]
                else:
                    print("not selected yet, skipped:", ds)
                    break
                for k in folds:
                    jobs += [line("s3", f"{ds}__{k}", "world", "none", s), line("s3", f"{ds}__{k}", "body", torque, s)]
    out = a.out or os.path.join(OUT, "jobs", f"{a.stage}_train.txt")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        f.writelines(jobs)
    print(len(jobs), "jobs in", out)


if __name__ == "__main__":
    main()
