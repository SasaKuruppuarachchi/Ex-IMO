#!/usr/bin/env python3
"""Build data/clean/ from data/raw/ by removing questionable data.

data/raw/ is never modified. Cleaning only removes whole files or contiguous
row ranges; every value that is kept is byte-identical to the source (CSV and
text rows are copied verbatim, HDF5 datasets are sliced without conversion).
No resampling, filtering, unit conversion or train/test re-splitting.

Rules (ids are used in cleaning_log.json and docs/CLEANING.md):
  R1  duplicate recording: byte-identical copies of another file -> keep the first
      (natural sort order), exclude the rest.
  R2  off-nominal sample rate: median rate deviates >1% from the dataset's nominal
      rate -> exclude.
  R3  synthetic edge: a core signal is an exact straight line in time (linear
      extrapolation) for >= SPAN_MIN_S at the start/end of a file -> trim it off.
  R4  synthetic-heavy file: after R3, > SYNTH_MAX_FRAC of the samples sit in interior
      synthetic spans (linear interpolation over missing data) -> exclude.
  R5  long interior gap: an interior synthetic span >= GAP_SPLIT_S -> remove it and
      split the file into parts.
  R6  too short: a recording, or a part created by R3/R5, shorter than MIN_PART_S
      -> drop. Not applied to NeuroBEM's author-curated segments.
  R7  physical range: any remaining NaN or out-of-range core value -> drop the part.
  R8  stray file: non-data files (editor swap files) are not copied.

Run inside the project container:
    docker/run.sh python3 data_prep/clean_datasets.py
"""
import argparse
import datetime
import glob
import hashlib
import json
import os
import re
import shutil
import sys

import h5py
import numpy as np
import pandas as pd

ROOT = os.environ.get("EXIMO_WORKSPACE", "/workspace")                           # holds data/{raw,clean,processed}
RAW = os.environ.get("EXIMO_RAW", os.path.join(ROOT, "data", "raw"))
CLEAN = os.environ.get("EXIMO_CLEAN", os.path.join(ROOT, "data", "clean"))
LOG = os.path.join(os.path.dirname(CLEAN), "cleaning_log.json")

SPAN_MIN_S = 0.10      # shortest straight-line run that counts as synthetic
GAP_SPLIT_S = 0.25     # interior synthetic spans at least this long are cut out
SYNTH_MAX_FRAC = 0.10  # files with more interior synthetic samples are excluded
MIN_PART_S = 5.0       # shortest recording/part kept (not for NeuroBEM segments)
RATE_TOL = 0.01


# --------------------------------------------------------------------- detection
def synthetic_runs(t, X, min_s):
    """[(first_row, last_row)] of maximal stretches where every column of X is an
    exact straight line in t with non-zero slope, lasting >= min_s. Both end rows
    are included; they are the extrapolation/interpolation knots."""
    t = np.asarray(t, float)
    X = np.asarray(X, float).reshape(len(t), -1)
    s = np.diff(X, axis=0) / np.diff(t)[:, None]
    same = (np.abs(np.diff(s, axis=0)) <= 1e-6 * (1 + np.abs(s[1:])) + 1e-6).all(axis=1)
    moving = (np.abs(s[1:]) > 1e-6).any(axis=1)
    inner = np.zeros(len(t), bool)
    inner[1:-1] = same & moving
    runs, i, n = [], 0, len(t)
    while i < n:
        if inner[i]:
            j = i
            while j < n and inner[j]:
                j += 1
            a, b = i - 1, min(j, n - 1)
            if t[b] - t[a] >= min_s:
                runs.append((a, b))
            i = j
        else:
            i += 1
    return runs


def merge(runs):
    out = []
    for a, b in sorted(runs):
        if out and a <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def plan(t, groups, ranges, nominal_hz, min_part_s):
    """Apply R2-R7 to one recording. Returns (kept [(a, b_exclusive)], removed [...], excluded_rule|None, info)."""
    t = np.asarray(t, float)
    n = len(t)
    info = {}
    hz = float(1 / np.median(np.diff(t)))
    info["rate_hz"] = round(hz, 2)
    if abs(hz / nominal_hz - 1) > RATE_TOL:
        return [], [], "R2", info
    spans = merge(r for X in groups.values() for r in synthetic_runs(t, X, SPAN_MIN_S))
    removed, lo, hi = [], 0, n
    for a, b in spans:
        if a == 0:                       # leading extrapolation: keep from the knot b
            lo = max(lo, b)
            removed.append(dict(rule="R3", rows=[0, b], t=[0.0, round(t[b] - t[0], 3)]))
        elif b == n - 1:                 # trailing extrapolation: keep up to the knot a
            hi = min(hi, a + 1)
            removed.append(dict(rule="R3", rows=[a + 1, n], t=[round(t[a] - t[0], 3), round(t[-1] - t[0], 3)]))
    interior = [(a, b) for a, b in spans if a > 0 and b < n - 1 and a >= lo and b < hi]
    synth = sum(b - a - 1 for a, b in interior)
    info["interior_synthetic_frac"] = round(synth / max(hi - lo, 1), 4)
    info["interior_synthetic_spans"] = len(interior)
    info["longest_interior_span_s"] = round(max((t[b] - t[a] for a, b in interior), default=0.0), 3)
    if hi - lo > 0 and synth / (hi - lo) > SYNTH_MAX_FRAC:
        return [], removed, "R4", info
    kept, start = [], lo
    for a, b in interior:
        if t[b] - t[a] >= GAP_SPLIT_S:
            kept.append((start, a + 1))
            removed.append(dict(rule="R5", rows=[a + 1, b], t=[round(t[a] - t[0], 3), round(t[b] - t[0], 3)]))
            start = b
    kept.append((start, hi))
    final = []
    for a, b in kept:
        dur = t[b - 1] - t[a] if b > a else 0.0
        if min_part_s and dur < min_part_s:
            removed.append(dict(rule="R6", rows=[a, b], t=[round(t[a] - t[0], 3), round(t[b - 1] - t[0], 3)]))
            continue
        bad = [name for name, (X, ok) in ranges.items() if not ok(np.asarray(X, float)[a:b]).all()]
        if bad:
            removed.append(dict(rule="R7", rows=[a, b], fields=bad))
            continue
        final.append((a, b))
    return final, removed, (None if final else ("R6" if removed and removed[-1]["rule"] == "R6" else "R7")), info


def finite_and(lo=-np.inf, hi=np.inf):
    return lambda X: np.isfinite(X).all(axis=-1) & (X >= lo).all(axis=-1) & (X <= hi).all(axis=-1) if X.ndim > 1 \
        else np.isfinite(X) & (X >= lo) & (X <= hi)


# ------------------------------------------------------------------------ writing
def write_csv_rows(src, dst, parts):
    """Copy header + selected data rows verbatim (row i of the table is line i+1)."""
    with open(src, newline="") as f:
        lines = f.readlines()
    outs = []
    for k, (a, b) in enumerate(parts, 1):
        p = dst if len(parts) == 1 else re.sub(r"(\.\w+)$", rf"__part{k}\1", dst)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", newline="") as f:
            f.write(lines[0])
            f.writelines(lines[a + 1:b + 1])
        outs.append(p)
    return outs


def write_text_rows(src, dst, parts, header_lines=1):
    with open(src, newline="") as f:
        lines = f.readlines()
    head, body = lines[:header_lines], lines[header_lines:]
    outs = []
    for k, (a, b) in enumerate(parts, 1):
        p = dst if len(parts) == 1 else re.sub(r"(\.\w+)$", rf"__part{k}\1", dst)
        with open(p, "w", newline="") as f:
            f.writelines(head + body[a:b])
        outs.append(p)
    return outs


def write_h5_rows(src, dst, parts):
    outs = []
    with h5py.File(src, "r") as h:
        n = h["ts"].shape[0]
        for k, (a, b) in enumerate(parts, 1):
            p = dst if len(parts) == 1 else re.sub(r"(\.\w+)$", rf"__part{k}\1", dst)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with h5py.File(p, "w") as o:
                for key, v in h.attrs.items():
                    o.attrs[key] = v
                for key, ds in h.items():
                    data = ds[a:b] if ds.ndim and ds.shape[0] == n else ds[()]
                    o.create_dataset(key, data=data, dtype=ds.dtype)
                    for ak, av in ds.attrs.items():
                        o[key].attrs[ak] = av
            outs.append(p)
    return outs


def copy(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)
    return [dst]


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while blk := f.read(1 << 20):
            h.update(blk)
    return h.hexdigest()


def natural(s):
    return [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", s)]


def entry(src, t, kept, removed, excluded, info, outs, rules_extra=()):
    t = np.asarray(t, float)
    rules = sorted({r["rule"] for r in removed} | ({excluded} if excluded else set()) | set(rules_extra))
    action = "excluded" if excluded else ("copied" if kept == [(0, len(t))] else
                                          "split" if len(kept) > 1 else "trimmed")
    return dict(
        source=os.path.relpath(src, RAW), action=action, rules=rules,
        rows_in=len(t), duration_in_s=round(float(t[-1] - t[0]), 3),
        rows_out=sum(b - a for a, b in kept),
        duration_out_s=round(float(sum(t[b - 1] - t[a] for a, b in kept)), 3),
        outputs=[dict(file=os.path.relpath(o, CLEAN), rows=[a, b],
                      t=[round(float(t[a] - t[0]), 3), round(float(t[b - 1] - t[0]), 3)])
                 for o, (a, b) in zip(outs, kept)],
        removed=removed, **info)


# ----------------------------------------------------------------------- datasets
def clean_nanobench():
    src_dir = os.path.join(RAW, "nanobench", "repo", "datasets", "dataset")
    dst_dir = os.path.join(CLEAN, "nanobench")
    csvs = sorted(glob.glob(os.path.join(src_dir, "*.csv")), key=lambda p: natural(os.path.basename(p)))
    first_by_hash, log = {}, []
    for f in csvs:
        name = os.path.basename(f)
        df = pd.read_csv(f)
        t = df["t"].to_numpy()
        h = sha256(f)
        if h in first_by_hash:   # R1
            log.append(entry(f, t, [], [], "R1", dict(duplicate_of=first_by_hash[h]), []))
            continue
        first_by_hash[h] = os.path.relpath(f, RAW)
        groups = dict(imu=df.filter(like="imu_"), motor=df.filter(like="motor_motor_m"), vicon=df[["px", "py", "pz"]])
        ranges = dict(motor_pwm=(df.filter(like="motor_motor_m"), finite_and(0, 65535)),
                      vbat_1s=(df["pwr_pm_vbat"], finite_and(2.5, 4.35)),
                      imu=(df.filter(like="imu_"), finite_and()), vicon=(df[["px", "py", "pz", "qw"]], finite_and()))
        kept, removed, excluded, info = plan(t, groups, ranges, 100.0, MIN_PART_S)
        outs = []
        if kept:
            outs = write_csv_rows(f, os.path.join(dst_dir, name), kept)
            copy(f.replace(".csv", "_metadata.yaml"), os.path.join(dst_dir, name.replace(".csv", "_metadata.yaml")))
        log.append(entry(f, t, kept, removed, excluded, info, outs))
    return log


def clean_ai_io():
    root = os.path.join(RAW, "ai_io", "AI-IO_dataset")
    log = []
    for f in sorted(glob.glob(os.path.join(root, "**", "data.hdf5"), recursive=True)):
        rel = os.path.relpath(f, root)
        with h5py.File(f, "r") as h:
            t = h["ts"][:]
            tt = h["traj_target"][:]
            groups = dict(imu=np.hstack([h["accel_raw"][:], h["gyro_raw"][:]]), motor=h["rotor_spd"][:],
                          gt_pos=tt[:, 0:3], gt_vel=tt[:, 7:10])
            ranges = dict(rotor_spd=(h["rotor_spd"][:], finite_and(0)), imu=(groups["imu"], finite_and()),
                          traj_target=(tt, finite_and()))
        kept, removed, excluded, info = plan(t, groups, ranges, 100.0, MIN_PART_S)
        outs = []
        if kept:
            dst = os.path.join(CLEAN, "ai_io", rel)
            outs = copy(f, dst) if kept == [(0, len(t))] else write_h5_rows(f, dst, kept)
            gt = f.replace("data.hdf5", "stamped_groundtruth_imu.txt")
            gdst = dst.replace("data.hdf5", "stamped_groundtruth_imu.txt")
            copy(gt, gdst) if kept == [(0, len(t))] else write_text_rows(gt, gdst, kept)
            meta = os.path.join(f.split(os.sep + "processed_data")[0], "metadata.yaml")
            copy(meta, os.path.join(CLEAN, "ai_io", os.path.relpath(meta, root)))
        log.append(entry(f, t, kept, removed, excluded, info, outs))
    return log


def clean_tii():
    root = os.path.join(RAW, "tii_ratm", "v3.0.0")
    log = []
    imu = ["accel_x", "accel_y", "accel_z", "gyro_x", "gyro_y", "gyro_z"]
    thrust = [f"thrust[{i}]" for i in range(4)]
    for fl in sorted(glob.glob(os.path.join(root, "*", "flight-*"))):
        fid = os.path.basename(fl)
        f500 = os.path.join(fl, f"{fid}_500hz_freq_sync.csv")
        fcam = os.path.join(fl, f"{fid}_cam_ts_sync.csv")
        df = pd.read_csv(f500, usecols=["elapsed_time", "vbat", "drone_x", "drone_y", "drone_z"] + imu + thrust)
        t = df["elapsed_time"].to_numpy()
        groups = dict(imu=df[imu], thrust=df[thrust], mocap=df[["drone_x", "drone_y", "drone_z"]])
        ranges = dict(thrust=(df[thrust], finite_and(0, 1)), imu=(df[imu], finite_and()),
                      mocap=(df[["drone_x", "drone_y", "drone_z"]], finite_and()))
        kept, removed, excluded, info = plan(t, groups, ranges, 500.0, MIN_PART_S)
        outs = []
        if kept:
            dst = os.path.join(CLEAN, "tii_ratm", os.path.relpath(f500, root))
            outs = copy(f500, dst) if kept == [(0, len(t))] else write_csv_rows(f500, dst, kept)
            cam_t = pd.read_csv(fcam, usecols=["elapsed_time"])["elapsed_time"].to_numpy()
            cam_parts = [(int(np.searchsorted(cam_t, t[a])), int(np.searchsorted(cam_t, t[b - 1], "right"))) for a, b in kept]
            cdst = os.path.join(CLEAN, "tii_ratm", os.path.relpath(fcam, root))
            copy(fcam, cdst) if kept == [(0, len(t))] else write_csv_rows(fcam, cdst, cam_parts)
            for m in glob.glob(os.path.join(fl, "metadata_*.yaml")):
                copy(m, os.path.join(CLEAN, "tii_ratm", os.path.relpath(m, root)))
        log.append(entry(f500, t, kept, removed, excluded, info, outs))
    return log


def clean_neurobem():
    src = os.path.join(RAW, "neurobem")
    log = []
    for f in sorted(glob.glob(os.path.join(src, "processed_data", "*"))):
        if not f.endswith(".csv"):  # R8 (glob skips dotfiles; listed explicitly below)
            continue
        df = pd.read_csv(f)
        df.columns = [c.strip() for c in df.columns]
        t = df["t"].to_numpy()
        imu = df[["acc x", "acc y", "acc z", "ang vel x", "ang vel y", "ang vel z"]]
        mot = df[["mot 1", "mot 2", "mot 3", "mot 4"]]
        groups = dict(imu=imu, motor=mot, gt_pos=df[["pos x", "pos y", "pos z"]])
        ranges = dict(motor_rad_s=(mot, finite_and(0)), imu=(imu, finite_and()),
                      gt=(df[["pos x", "pos y", "pos z", "quat w", "vel x"]], finite_and()))
        kept, removed, excluded, info = plan(t, groups, ranges, 400.0, 0.0)
        outs = []
        if kept:
            dst = os.path.join(CLEAN, "neurobem", "processed_data", os.path.basename(f))
            outs = copy(f, dst) if kept == [(0, len(t))] else write_csv_rows(f, dst, kept)
        log.append(entry(f, t, kept, removed, excluded, info, outs))
    for p in glob.glob(os.path.join(src, "processed_data", ".*")):
        log.append(dict(source=os.path.relpath(p, RAW), action="excluded", rules=["R8"], note="editor swap file"))
    for name in ("Flights.txt", "testset.txt", "Readme.md"):
        copy(os.path.join(src, name), os.path.join(CLEAN, "neurobem", name))
    return log


def summarize(log):
    rec = [e for e in log if "rows_in" in e]
    by_action = {}
    for e in log:
        by_action[e["action"]] = by_action.get(e["action"], 0) + 1
    by_rule = {}
    for e in log:
        for r in e["rules"]:
            by_rule[r] = by_rule.get(r, 0) + 1
    return dict(
        files_in=len(rec), files_kept=sum(e["action"] != "excluded" for e in rec),
        output_sequences=sum(len(e["outputs"]) for e in rec),
        duration_in_min=round(sum(e["duration_in_s"] for e in rec) / 60, 2),
        duration_out_min=round(sum(e["duration_out_s"] for e in rec) / 60, 2),
        actions=by_action, files_per_rule=by_rule)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", nargs="*", choices=["nanobench", "ai_io", "tii_ratm", "neurobem"])
    a = ap.parse_args()
    fns = dict(nanobench=clean_nanobench, ai_io=clean_ai_io, tii_ratm=clean_tii, neurobem=clean_neurobem)
    out = dict(generated_by="data_prep/clean_datasets.py",
               generated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
               thresholds=dict(SPAN_MIN_S=SPAN_MIN_S, GAP_SPLIT_S=GAP_SPLIT_S, SYNTH_MAX_FRAC=SYNTH_MAX_FRAC,
                               MIN_PART_S=MIN_PART_S, RATE_TOL=RATE_TOL),
               datasets={})
    if os.path.exists(LOG) and a.only:
        out["datasets"] = json.load(open(LOG))["datasets"]
    for name, fn in fns.items():
        if a.only and name not in a.only:
            continue
        shutil.rmtree(os.path.join(CLEAN, name), ignore_errors=True)
        log = fn()
        out["datasets"][name] = dict(summary=summarize(log), files=log)
        s = out["datasets"][name]["summary"]
        print(f"{name:10s} files {s['files_in']:4d} -> kept {s['files_kept']:4d} ({s['output_sequences']} sequences), "
              f"{s['duration_in_min']:7.1f} -> {s['duration_out_min']:7.1f} min  actions={s['actions']} rules={s['files_per_rule']}")
    with open(LOG, "w") as f:
        json.dump(out, f, indent=1)
    print(f"wrote {os.path.relpath(LOG, ROOT)}")


if __name__ == "__main__":
    sys.exit(main())
