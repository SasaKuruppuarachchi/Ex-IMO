"""Is body_rotor's validation gain real information, or an artefact? On CPU, validation split only.

1. Corrupt the torque channels of a trained body_rotor model and watch the error:
       zero, swapped between windows of a flight (same distribution, wrong time), delayed, reversed in time, window mean only.
   Mean-only close to intact means a slow signal is doing the work, such as trim against airspeed, not the transient.
2. Ridge from one window of a single input to the displacement target, fitted on train: how much velocity each input carries.
3. Per-flight error of body_gyro and body_rotor, to see whether a few flights carry the gain.

    python3 scripts/diag/rotor_gain_check.py --dataset ai_io --seed 42
"""
import argparse
import json
import os

import numpy as np
import torch

from learning.data_management.features import input_dim
from learning.data_management.windows import WindowData, get_datalist
from learning.network.model_factory import get_model

from eximo_paths import DATA, RESULTS

RES = os.path.join(RESULTS, "s1")
W = 50
TAU = slice(6, 9)


def load(ds, variant, seed):
    d = f"{RES}/{ds}/{variant}/seed{seed}/{ds}/checkpoints/model_net"
    with open(os.path.join(d, "model_net_parameters.json")) as f:
        p = json.load(f)
    net = get_model(input_dim(p["torque"]), 3)
    net.load_state_dict(torch.load(os.path.join(d, "checkpoint_best.pt"), map_location="cpu", weights_only=False)["model_state_dict"])
    return net.eval(), p


def data(ds, names, torque, stride, g):
    return WindowData(DATA, ds, names, W, frame="body", torque=torque, stride=stride, g=g)


def errors(net, d, corrupt=None):
    out = []
    with torch.no_grad():
        for k in range(0, len(d), 2048):
            idx = np.arange(k, min(k + 2048, len(d)))
            x, y = d.batch(idx)
            if corrupt:
                corrupt(x, idx, d)
            out.append(np.linalg.norm(net(torch.from_numpy(x)).numpy() - y, axis=1))
    return np.concatenate(out)


def rmse(e):
    return float(np.sqrt((e ** 2).mean()))


def swap_within_flight(rng, d):
    perm = np.arange(len(d))
    for k in np.unique(d.seq_ids):
        m = np.where(d.seq_ids == k)[0]
        perm[m] = rng.permutation(m)

    def f(x, idx, d):
        x[:, TAU] = d.batch(perm[idx])[0][:, TAU]
    return f


def delayed(steps):
    def f(x, idx, d):
        win = np.maximum(d.starts[idx] - steps, 0)[:, None] + np.arange(W)
        x[:, TAU] = d.tau[win].transpose(0, 2, 1)
    return f


def zero(x, idx, d):
    x[:, TAU] = 0


def reverse(x, idx, d):
    x[:, TAU] = x[:, TAU][:, :, ::-1]


def mean_only(x, idx, d):
    x[:, TAU] = x[:, TAU].mean(axis=2, keepdims=True)


def inputs(d, every=5):
    X, Y = [], []
    for k in range(0, len(d), 4096):
        x, y = d.batch(np.arange(k, min(k + 4096, len(d))))
        X.append(x[:, :, ::every])
        Y.append(y)
    return np.concatenate(X), np.concatenate(Y)


def ridge_r2(Xtr, Ytr, Xva, Yva, ch):
    a, b = Xtr[:, ch].reshape(len(Xtr), -1), Xva[:, ch].reshape(len(Xva), -1)
    mu, sd = a.mean(0), a.std(0) + 1e-9
    a, b = (a - mu) / sd, (b - mu) / sd
    ym = Ytr.mean(0)
    w = np.linalg.solve(a.T @ a + 1e-3 * len(a) * np.eye(a.shape[1]), a.T @ (Ytr - ym))
    return 1 - ((b @ w + ym - Yva) ** 2).sum(0) / ((Yva - Yva.mean(0)) ** 2).sum(0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--stride", type=int, default=5)
    a = ap.parse_args()
    ds, rng = a.dataset, np.random.default_rng(0)
    val = get_datalist(f"{DATA}/{ds}/val.txt")
    train = get_datalist(f"{DATA}/{ds}/train.txt")
    rotor, p = load(ds, "body_rotor", a.seed)
    gyro, _ = load(ds, "body_gyro", a.seed)
    d_rotor = data(ds, val, "rotor", a.stride, p["g_norm"])
    d_gyro = data(ds, val, "gyro", a.stride, p["g_norm"])
    print(f"== {ds} seed {a.seed}: {len(d_rotor)} val windows in {len(val)} flights")
    base = errors(rotor, d_rotor)
    print(f"body_gyro intact        {rmse(errors(gyro, d_gyro)):.4f} m")
    print(f"body_rotor intact       {rmse(base):.4f} m")
    for name, c in [("tau zeroed", zero), ("tau swapped in flight", swap_within_flight(rng, d_rotor)),
                    ("tau delayed 50 ms", delayed(5)), ("tau delayed 200 ms", delayed(20)), ("tau delayed 1 s", delayed(100)),
                    ("tau reversed in window", reverse), ("tau window mean only", mean_only)]:
        print(f"body_rotor {name:<24s}{rmse(errors(rotor, d_rotor, c)):.4f} m")
    tr_r = data(ds, train, "rotor", max(a.stride, 10), p["g_norm"])
    tr_g = data(ds, train, "gyro", max(a.stride, 10), p["g_norm"])
    Xtr, Ytr = inputs(tr_r)
    Xva, Yva = inputs(d_rotor)
    Gtr, _ = inputs(tr_g)
    Gva, _ = inputs(d_gyro)
    print("ridge R2 of the body displacement (x, y, z) on val, from one window:")
    for name, x, xv, ch in [("gyro", Xtr, Xva, [0, 1, 2]), ("specific force", Xtr, Xva, [3, 4, 5]), ("tau_gyro", Gtr, Gva, [6, 7, 8]),
                            ("tau_rotor", Xtr, Xva, [6, 7, 8]), ("gyro + force", Xtr, Xva, [0, 1, 2, 3, 4, 5]),
                            ("gyro + force + tau_rotor", Xtr, Xva, list(range(9)))]:
        r = ridge_r2(x, Ytr, xv, Yva, ch)
        print(f"  {name:<26s}{r[0]:7.3f} {r[1]:7.3f} {r[2]:7.3f}")
    print("per flight, RMSE [m]: body_gyro body_rotor")
    eg = errors(gyro, d_gyro)
    for k, name in enumerate(val):
        m = d_rotor.seq_ids == k
        if m.any():
            print(f"  {name:<46s}{rmse(eg[d_gyro.seq_ids == k]):7.3f} {rmse(base[m]):7.3f}")


if __name__ == "__main__":
    main()
