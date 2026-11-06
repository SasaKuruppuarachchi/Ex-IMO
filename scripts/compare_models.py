"""Compare models against a baseline from per-sequence CSVs (see eval_filter.py).

--csv NAME:SEED:PATH (repeatable). For each model/metric: mean +- std across
seeds of the per-seed sequence-mean, % change vs baseline, a paired t-test
across seeds (per-seed means) and a Wilcoxon signed-rank test across sequences
(per-sequence values averaged over seeds). Sequences with NaN for the metric in
either model (any seed) are dropped pairwise before the tests; the displayed
mean +- std use each model's own valid sequences. p-values are only printed.
"""

import argparse
from collections import defaultdict

import numpy as np
import pandas as pd
from scipy import stats


def load_runs(specs):
    """specs: 'NAME:SEED:PATH' -> {name: {seed: DataFrame indexed by sequence}}."""
    runs = defaultdict(dict)
    for s in specs:
        name, seed, path = s.split(":", 2)
        runs[name][seed] = pd.read_csv(path).set_index("sequence")
    return runs


def _table(runs_m, metric):
    """DataFrame sequences x seeds for one model."""
    return pd.DataFrame({sd: pd.to_numeric(df[metric], errors="coerce") for sd, df in runs_m.items()})


def compare(runs, baseline, metrics):
    rows = []
    for metric in metrics:
        tabs = {m: _table(r, metric) for m, r in runs.items()}
        base = tabs[baseline]
        base_mean = np.nanmean(base.mean(axis=0).values)
        for m, tab in tabs.items():
            seed_means = tab.mean(axis=0, skipna=True)  # per seed, own valid sequences
            r = dict(metric=metric, model=m, n_seeds=len(tab.columns),
                     mean=float(seed_means.mean()),
                     std=float(seed_means.std(ddof=1)) if len(seed_means) > 1 else np.nan,
                     pct_change=np.nan, t_p=np.nan, n_t=0, w_p=np.nan, n_w=0, dropped=0,
                     warn="")
            if m != baseline:
                r["pct_change"] = 100 * (r["mean"] - base_mean) / base_mean if base_mean else np.nan
                seqs = tab.index.intersection(base.index)
                ok = tab.loc[seqs].notna().all(axis=1) & base.loc[seqs].notna().all(axis=1)
                r["dropped"] = len(seqs) - int(ok.sum())
                a, b = tab.loc[seqs][ok], base.loc[seqs][ok]
                seeds = [s for s in a.columns if s in b.columns]
                r["n_t"] = len(seeds)
                if len(seeds) >= 2 and len(a) > 0:
                    d = a[seeds].mean(axis=0).values - b[seeds].mean(axis=0).values
                    if np.allclose(d, d[0]) and d[0] == 0:
                        r["t_p"] = 1.0
                    else:
                        r["t_p"] = float(stats.ttest_rel(a[seeds].mean(axis=0).values,
                                                         b[seeds].mean(axis=0).values).pvalue)
                da, db = a.mean(axis=1).values, b.mean(axis=1).values
                r["n_w"] = len(da)
                if len(da) >= 1 and np.any(da != db):
                    try:
                        r["w_p"] = float(stats.wilcoxon(da, db).pvalue)
                    except ValueError:
                        pass
                elif len(da) >= 1:
                    r["w_p"] = 1.0
                if min(len(seeds), len(tab.columns), len(base.columns)) < 3:
                    r["warn"] = f"n_seeds<3 (common seeds={len(seeds)})"
            elif len(tab.columns) < 3:
                r["warn"] = "n_seeds<3"
            rows.append(r)
    return rows


def format_markdown(rows, baseline):
    f = lambda x, p=4: "n/a" if x is None or not np.isfinite(x) else f"{x:.{p}g}"
    lines = [f"Baseline: {baseline}. Tests are paired vs baseline; p-values only, no threshold applied.", "",
             "| metric | model | mean +- std (over seeds) | n_seeds | % vs base | t-test p (n seeds) | Wilcoxon p (n seq) | seqs dropped (NaN) | warning |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        base = r["model"] == baseline
        name = r["model"] + (" (baseline)" if base else "")
        pc = "-" if base else f(r["pct_change"], 3)
        tp = "-" if base else "%s (n=%d)" % (f(r["t_p"]), r["n_t"])
        wp = "-" if base else "%s (n=%d)" % (f(r["w_p"]), r["n_w"])
        dr = "-" if base else str(r["dropped"])
        lines.append("| %s | %s | %s +- %s | %d | %s | %s | %s | %s | %s |" % (
            r["metric"], name, f(r["mean"]), f(r["std"]), r["n_seeds"], pc, tp, wp, dr, r["warn"]))
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", action="append", required=True, help="NAME:SEED:PATH, repeatable")
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--metrics", nargs="+", required=True)
    ap.add_argument("--out", default=None, help="write markdown here")
    args = ap.parse_args(argv)
    runs = load_runs(args.csv)
    if args.baseline not in runs:
        raise SystemExit(f"baseline {args.baseline!r} not among models {sorted(runs)}")
    md = format_markdown(compare(runs, args.baseline, args.metrics), args.baseline)
    print(md)
    if args.out:
        with open(args.out, "w") as fh:
            fh.write(md + "\n")


if __name__ == "__main__":
    main()
