"""
Train a displacement network: IMO (world frame), Ex-IMO (body frame + torque) or a variant between them.

    python3 src/train_ex.py --root_dir $EXIMO_OUT/data --dataset tii_ratm --frame body --torque gyro \
        --seed 42 --out_dir $EXIMO_OUT/results/<run>

Architecture, optimiser and window as upstream (train_model_net.py). Differences, all documented in docs/EX_IMO.md:
MSE on the displacement norm; seeded; whole validation set each time; a budget in steps, as sequence counts differ a
lot across datasets, with early stopping once validation has not improved for --patience_steps. Writes <out_dir>/<dataset>/checkpoints/model_net/{checkpoint_best,checkpoint_final}.pt,
model_net_parameters.json and train_log.csv.
"""
import argparse
import json
import os
import random
import time

import numpy as np
import torch

from learning.data_management.features import input_dim
from learning.data_management.windows import WindowData, get_datalist
from learning.network.model_factory import get_model


def evaluate(net, data, device, batch=1024):
    net.eval()
    se, n = 0.0, 0
    with torch.no_grad():
        for k in range(0, len(data), batch):
            feat, targ = data.batch(np.arange(k, min(k + batch, len(data))))
            e = net(torch.from_numpy(feat).to(device)).cpu().numpy() - targ
            se += (e ** 2).sum()
            n += len(e)
    net.train()
    return float(np.sqrt(se / n))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root_dir", required=True)
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--out_dir", required=True)
    ap.add_argument("--train_list", default="train.txt")
    ap.add_argument("--val_list", default="val.txt")
    ap.add_argument("--frame", default="world", choices=("world", "body"))
    ap.add_argument("--torque", default="none", choices=("none", "gyro", "rotor"))
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--batch_size", type=int, default=128)
    ap.add_argument("--max_steps", type=int, default=300000)
    ap.add_argument("--val_every", type=int, default=2000)
    ap.add_argument("--patience_steps", type=int, default=60000, help="0 = no early stopping")
    ap.add_argument("--imu_freq", type=float, default=100.0)
    ap.add_argument("--window_time", type=float, default=0.5)
    ap.add_argument("--g_norm", type=float, default=9.81)
    ap.add_argument("--sigma_ori_deg", type=float, default=2.0)
    ap.add_argument("--sigma_bg", type=float, default=0.005)
    ap.add_argument("--cpu", action="store_true")
    a = ap.parse_args()

    random.seed(a.seed)
    np.random.seed(a.seed)
    torch.manual_seed(a.seed)
    rng = np.random.default_rng(a.seed)
    device = torch.device("cuda:0" if torch.cuda.is_available() and not a.cpu else "cpu")

    window = int(round(a.window_time * a.imu_freq))
    kw = dict(window=window, frame=a.frame, torque=a.torque, g=a.g_norm)
    root = os.path.join(a.root_dir, a.dataset)
    train = WindowData(a.root_dir, a.dataset, get_datalist(os.path.join(root, a.train_list)),
                       sigma_ori_deg=a.sigma_ori_deg, sigma_bg=a.sigma_bg, **kw)
    val = WindowData(a.root_dir, a.dataset, get_datalist(os.path.join(root, a.val_list)), stride=5, **kw)

    out = os.path.join(a.out_dir, a.dataset, "checkpoints", "model_net")
    os.makedirs(out, exist_ok=True)
    params = dict(vars(a), sampling_freq=a.imu_freq, input_dim=input_dim(a.torque), output_dim=3)
    with open(os.path.join(out, "model_net_parameters.json"), "w") as f:
        json.dump(params, f, indent=4, sort_keys=True)

    net = get_model(input_dim(a.torque), 3).to(device)
    opt = torch.optim.Adam(net.parameters(), a.lr)
    print(f"{a.dataset} frame={a.frame} torque={a.torque} seed={a.seed} device={device}: {len(train)} train / "
          f"{len(val)} val windows, {net.get_num_params()} parameters", flush=True)

    def save(name, step, val_rmse):
        torch.save(dict(model_state_dict=net.state_dict(), step=step, val_rmse=val_rmse, args=vars(a)),
                   os.path.join(out, name))

    best, best_step, step, t0, stop = np.inf, 0, 0, time.time(), False
    log = open(os.path.join(out, "train_log.csv"), "w")
    log.write("step,train_rmse,val_rmse,seconds\n")
    run_se, run_n = 0.0, 0
    net.train()
    while step < a.max_steps and not stop:
        order = rng.permutation(len(train))
        for k in range(0, len(order) - a.batch_size + 1, a.batch_size):
            feat, targ = train.batch(order[k:k + a.batch_size], rng)
            feat, targ = torch.from_numpy(feat).to(device), torch.from_numpy(targ).to(device)
            loss = ((net(feat) - targ) ** 2).sum(dim=1).mean()
            opt.zero_grad()
            loss.backward()
            opt.step()
            step += 1
            run_se, run_n = run_se + loss.item(), run_n + 1
            if step % a.val_every == 0 or step == a.max_steps:
                v = evaluate(net, val, device)
                log.write(f"{step},{np.sqrt(run_se / run_n):.5f},{v:.5f},{time.time() - t0:.0f}\n")
                log.flush()
                print(f"step {step} train {np.sqrt(run_se / run_n):.4f} val {v:.4f} m ({time.time() - t0:.0f} s)", flush=True)
                run_se, run_n = 0.0, 0
                if v < best:
                    best, best_step = v, step
                    save("checkpoint_best.pt", step, v)
                elif a.patience_steps and step - best_step >= a.patience_steps:
                    print(f"early stop at step {step}: best at step {best_step}", flush=True)
                    stop = True
            if step >= a.max_steps or stop:
                break
    save("checkpoint_final.pt", step, v)
    print(f"done: best val {best:.4f} m", flush=True)


if __name__ == "__main__":
    main()
