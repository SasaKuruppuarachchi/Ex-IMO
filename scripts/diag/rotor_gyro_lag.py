"""Timing between rotor signals and gyro, and what it does to the allocation fit (training split only).

For each lag, per axis: least squares of dw/dt on the 4 per-motor thrusts + intercept. Reports R^2 and the gain
||A_row||, at several smoothing bandwidths. Attenuated gains at zero lag with a clear peak elsewhere mean the logs
are offset; flat low R^2 means the rotors don't explain the rate derivative at that bandwidth.
"""
import json, os, sys
import numpy as np
from scipy.signal import savgol_filter
sys.path.insert(0, "src/learning/data_management/prepare_datasets")
import public_uav_imo as P

for ds in P.DATASETS:
    th = json.load(open(f"config/physics/{ds}.json"))["thrust"]
    seqs = [P.load_sequence(p) for n, sp, p in P.find_sequences(ds) if sp == "train"]
    seqs = [s for s in seqs if len(s["ts"]) > 120]
    print(f"\n== {ds}: {len(seqs)} sequences (>1.2 s). Body-rate derivative R^2 / row gain vs rotor lag")
    for win in (7, 21):
        print(f" savgol window {win} samples ({win*10} ms)")
        for lag in (-10, -5, -3, -2, -1, 0, 1, 2, 3, 5, 10, 15, 20):
            r2, g, r2g = [], [], []
            F, D, W = [], [], []
            for s in seqs:
                f = P.collective_thrust(s, th)
                m = P.flying_mask(s, f)
                dt = np.median(np.diff(s["ts"]))
                d = savgol_filter(s["gyro_calib"], win, 3, deriv=1, delta=dt, axis=0)
                ff = savgol_filter(f, win, 3, axis=0)
                w = P.gyroscopic_products(savgol_filter(s["gyro_calib"], win, 3, axis=0))
                # lag > 0: rotor sample k explains the rate derivative at k + lag
                if lag > 0:
                    F.append(ff[:-lag][m[:-lag]]); D.append(d[lag:][m[:-lag]]); W.append(w[lag:][m[:-lag]])
                elif lag < 0:
                    F.append(ff[-lag:][m[-lag:]]); D.append(d[:lag][m[-lag:]]); W.append(w[:lag][m[-lag:]])
                else:
                    F.append(ff[m]); D.append(d[m]); W.append(w[m])
            F, D, W = map(np.concatenate, (F, D, W))
            row, cs = [], []
            for k in range(3):
                X = np.c_[F, np.ones(len(F)), -W[:, k]]
                sol = np.linalg.lstsq(X, D[:, k], rcond=None)[0]
                row.append((1 - (D[:, k] - X @ sol).var() / D[:, k].var(), np.linalg.norm(sol[:4]) / 2, sol[5]))
            print(f"  lag {lag*10:+4d} ms  R2 " + " ".join(f"{r[0]:6.3f}" for r in row) +
                  "   gain " + " ".join(f"{r[1]:6.1f}" for r in row) + "   c " + " ".join(f"{r[2]:6.2f}" for r in row))
