"""Position samples inconsistent with the logged velocity. IMO's target is built from position, so a jump corrupts every
window spanning it; AI-IO trains on velocity and don't see it. Flags steps where |dp/dt - v| > --thr m/s."""
import argparse
import os

import h5py
import numpy as np

from eximo_paths import DATA
from learning.data_management.windows import get_datalist

ap = argparse.ArgumentParser()
ap.add_argument("--root_dir", default=DATA)
ap.add_argument("--thr", type=float, default=5.0)
a = ap.parse_args()
for ds in ("ai_io", "nanobench", "tii_ratm", "neurobem"):
    lists = [l for l in ("train", "val", "test", "unseen") if os.path.exists(os.path.join(a.root_dir, ds, l + ".txt"))]
    total, flagged = 0, 0
    print(f"== {ds}")
    for l in lists:
        for n in get_datalist(os.path.join(a.root_dir, ds, l + ".txt")):
            with h5py.File(os.path.join(a.root_dir, ds, n, "data.hdf5"), "r") as f:
                t, p, v = f["ts"][()], f["traj_target"][:, :3], f["traj_target_v"][()]
            dt = np.diff(t)
            r = np.linalg.norm(np.diff(p, axis=0) / dt[:, None] - v[:-1], axis=1)
            bad = np.where(r > a.thr)[0]
            total += len(r)
            flagged += len(bad)
            if len(bad):
                steps = np.linalg.norm(np.diff(p, axis=0), axis=1)[bad]
                print(f"  {n}: {len(bad)} of {len(r)} steps, at t = {t[bad[0]] - t[0]:.2f} .. {t[bad[-1]] - t[0]:.2f} s, "
                      f"largest step {steps.max():.3f} m, |v-dp/dt| max {r.max():.1f} m/s, |v-dp/dt| median {np.median(r):.3f}")
    print(f"  total flagged {flagged} of {total}")
