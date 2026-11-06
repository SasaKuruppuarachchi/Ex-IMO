"""Tables of a stage: each variant against base IMO, over seeds, as in results/ex_imo/.

    python3 scripts/compare_stage.py --stage s1 --dataset ai_io
    python3 scripts/compare_stage.py --stage s3 --dataset neurobem__circles --variants world_none body_rotor

Runs scripts/compare_models.py on <results>/<stage>/<dataset>/<variant>/seed<k>/<list>_{filter,net}.csv (written by
select_and_test.py) and writes <results>/<stage>/compare/<dataset>_<list>_<kind>.md.
"""
import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
from eximo_paths import RESULTS  # noqa: E402

METRICS = dict(filter=["vel_RMSE", "ATE_se3", "RE_T", "ATE_none", "nees_median"], net=["RMSE", "AVE"])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stage", required=True)
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--variants", nargs="+", default=["world_none", "body_gyro", "body_rotor"])
    ap.add_argument("--seeds", nargs="+", default=["42", "43", "44"])
    ap.add_argument("--lists", nargs="+", default=["test", "unseen"])
    a = ap.parse_args()
    out = os.path.join(RESULTS, a.stage, "compare")
    os.makedirs(out, exist_ok=True)
    for lst in a.lists:
        for kind, metrics in METRICS.items():
            csvs = [(v, s, os.path.join(RESULTS, a.stage, a.dataset, v, f"seed{s}", f"{lst}_{kind}.csv")) for v in a.variants for s in a.seeds]
            if not all(os.path.exists(p) for _, _, p in csvs):
                continue
            cmd = [sys.executable, os.path.join(HERE, "compare_models.py"), "--baseline", a.variants[0], "--metrics", *metrics,
                   "--out", os.path.join(out, f"{a.dataset}_{lst}_{kind}.md")]
            for v, s, p in csvs:
                cmd += ["--csv", f"{v}:{s}:{p}"]
            print(f"## {a.dataset} {lst} {kind}", flush=True)
            subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
