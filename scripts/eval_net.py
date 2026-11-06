"""Network-only metrics per sequence, with ground-truth attitude, on CPU.

    python3 scripts/eval_net.py --root_dir <data> --dataset tii_ratm --model_dir <...>/model_net --list test.txt --out net.csv

dp_RMSE = sqrt(mean ||dp_hat - dp||^2) [m]. AVE and RMSE divide the error by the window time: they are errors of the mean
velocity over the window, in the model's output frame. AI-IO predicts an instantaneous body velocity over a 1 s
window, so these are close to, but not the same quantity as, their AVE and RMSE. The filter's vel_RMSE is the same quantity.
--yaw_deg evaluates with that heading error in the input attitude, to measure the coupling of attitude and motion.
--world_yaw_deg rotates the flight as a whole. A model that learned dynamics doesn't change; one that memorised the
track's headings does. Body-frame models are invariant by construction.
"""
import argparse
import json
import os

import numpy as np
import pandas as pd
import torch
from scipy.spatial.transform import Rotation

from learning.data_management.features import input_dim
from learning.data_management.windows import WindowData, get_datalist
from learning.network.model_factory import get_model


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root_dir", required=True)
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--model_dir", required=True)
    ap.add_argument("--checkpoint", default="checkpoint_best.pt")
    ap.add_argument("--list", default="test.txt")
    ap.add_argument("--yaw_deg", type=float, default=0.0)
    ap.add_argument("--world_yaw_deg", type=float, default=0.0,
                    help="rotate the whole flight about z, input and target: physically the same flight in another world frame")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    with open(os.path.join(a.model_dir, "model_net_parameters.json")) as f:
        p = json.load(f)
    net = get_model(input_dim(p["torque"]), 3)
    net.load_state_dict(torch.load(os.path.join(a.model_dir, a.checkpoint), map_location="cpu", weights_only=False)["model_state_dict"])
    net.eval()
    window = int(round(p["window_time"] * p["imu_freq"]))
    rows = []
    for name in get_datalist(os.path.join(a.root_dir, a.dataset, a.list)):
        d = WindowData(a.root_dir, a.dataset, [name], window, frame=p["frame"], torque=p["torque"], g=p["g_norm"])
        if len(d) == 0:
            rows.append(dict(sequence=name, n=0))
            continue
        if a.world_yaw_deg:
            R_z = Rotation.from_euler("z", a.world_yaw_deg, degrees=True).as_matrix()
            d.R, d.p = R_z @ d.R, d.p @ R_z.T
        if a.yaw_deg:
            R_err = Rotation.from_euler("z", a.yaw_deg, degrees=True).as_matrix()
            R_true, d.R = d.R, R_err @ d.R
        errs = []
        with torch.no_grad():
            for k in range(0, len(d), 2048):
                idx = np.arange(k, min(k + 2048, len(d)))
                feat, targ = d.batch(idx)
                if a.yaw_deg:                                                      # the target stays in the true frame
                    s = d.starts[idx]
                    dp = d.p[s + window] - d.p[s]
                    targ = np.einsum("nji,nj->ni", R_true[s], dp) if p["frame"] == "body" else dp
                errs.append(net(torch.from_numpy(feat)).numpy() - targ)
        e = np.concatenate(errs)
        n = np.linalg.norm(e, axis=1)
        rows.append(dict(sequence=name, n=len(e), dp_RMSE=np.sqrt((n ** 2).mean()), dp_mean=n.mean(),
                         AVE=n.mean() / p["window_time"], RMSE=np.sqrt((n ** 2).mean()) / p["window_time"]))
    df = pd.DataFrame(rows)
    df.to_csv(a.out, index=False)
    print(a.dataset, a.list, f"frame={p['frame']} torque={p['torque']} yaw={a.yaw_deg} world_yaw={a.world_yaw_deg}: sequences {len(df)}, "
          f"pooled RMSE {np.sqrt(((df.RMSE ** 2) * df.n).sum() / df.n.sum()):.3f} m/s, mean AVE {df.AVE.mean():.3f}")


if __name__ == "__main__":
    main()
