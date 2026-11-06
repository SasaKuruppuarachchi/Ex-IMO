"""Held-out-trajectory summary for the README: change of EX-IMO (rotor torque) vs base IMO, from the result tables.

    python3 scripts/plots/heldout_plot.py            # writes docs/figures/heldout_{light,dark}.png

Bars are the mean over 3 seeds of the filter's velocity RMSE and ATE after SE(3) alignment; faded bars have a paired
t-test p >= 0.05 across seeds.
"""
import os
import re

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RES = os.path.join(REPO, "results", "ex_imo")
OUT = os.path.join(REPO, "docs", "figures")

ROWS = [  # (table, label)
    ("s1/ai_io_unseen_filter.md", "AI-IO  patterned flights"),
    ("s3/neurobem__circles_unseen_filter.md", "NeuroBEM  circles"),
    ("s3/neurobem__lemniscate_cpc_unseen_filter.md", "NeuroBEM  lemniscate, CPC"),
    ("s3/nanobench__crossing_unseen_filter.md", "NanoBench  figure-8, star, trefoil"),
    ("s3/nanobench__round_unseen_filter.md", "NanoBench  circle, oval, helix"),
    ("s3/tii_ratm__ellipse_unseen_filter.md", "TII-RATM  ellipse"),
    ("s3/tii_ratm__lemniscate_unseen_filter.md", "TII-RATM  lemniscate"),
    ("s3/tii_ratm__trackRATM_unseen_filter.md", "TII-RATM  race track"),
]
METRICS = [("vel_RMSE", "Velocity RMSE"), ("ATE_se3", "Position error (ATE)")]
THEMES = {
    "light": dict(text="#0b0b0b", muted="#52514e", grid="#d9d8d3", better="#2a78d6", worse="#e34948"),
    "dark": dict(text="#f0efec", muted="#c3c2b7", grid="#3a3a37", better="#3987e5", worse="#e66767"),
}


def read_table(path):
    """{metric: (% vs base, t-test p)} for the body_rotor rows."""
    out = {}
    for line in open(path):
        c = [x.strip() for x in line.split("|")]
        if len(c) > 6 and c[2] == "body_rotor":
            out[c[1]] = (float(c[5]), float(re.match(r"[\d.e+-]+", c[6]).group()))
    return out


def plot(rows, theme, path):
    t = THEMES[theme]
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "text.color": t["text"]})
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.6), sharey=True, gridspec_kw=dict(wspace=0.08))
    fig.subplots_adjust(left=0.235, right=0.99)
    y = list(range(len(rows)))[::-1]
    for ax, (m, title) in zip(axes, METRICS):
        for yi, (_, vals) in zip(y, rows):
            pct, p = vals[m]
            color = t["better"] if pct < 0 else t["worse"]
            ax.barh(yi, pct, height=0.62, color=color, alpha=1.0 if p < 0.05 else 0.35, linewidth=0)
            label = f"{pct:+.0f}%".replace("-", "−") + ("" if p < 0.05 else "  n.s.")
            ax.text(pct + (-2 if pct < 0 else 2), yi, label, va="center", ha="right" if pct < 0 else "left",
                    color=t["text"] if p < 0.05 else t["muted"], fontsize=9)
        ax.axvline(0, color=t["muted"], linewidth=1)
        ax.set_xlim(-100, 85)
        ax.set_title(title, loc="left", fontsize=11, color=t["text"], fontweight="bold")
        ax.xaxis.grid(True, color=t["grid"], linewidth=0.6)
        ax.set_axisbelow(True)
        ax.tick_params(colors=t["muted"], length=0)
        ax.set_xticks([-80, -40, 0, 40, 80])
        ax.set_xticklabels(["−80%", "−40%", "0", "+40%", "+80%"])
        for s in ax.spines.values():
            s.set_visible(False)
        ax.set_facecolor("none")
    axes[0].set_yticks(y)
    axes[0].set_yticklabels([label for label, _ in rows], color=t["text"])
    fig.suptitle("EX-IMO vs base IMO on trajectories never seen in training", x=0.0, ha="left", y=1.02,
                 fontsize=13, fontweight="bold", color=t["text"])
    fig.text(0.0, 0.955, "Change in error, mean of 3 seeds (lower is better). Faded: paired t-test p ≥ 0.05. "
             "Rotor-derived torque; filter tuned on validation.", ha="left", fontsize=9, color=t["muted"])
    fig.savefig(path, dpi=200, bbox_inches="tight", transparent=True)
    plt.close(fig)


def main():
    rows = [(label, read_table(os.path.join(RES, f))) for f, label in ROWS]
    os.makedirs(OUT, exist_ok=True)
    for theme in THEMES:
        plot(rows, theme, os.path.join(OUT, f"heldout_{theme}.png"))
        print("wrote", os.path.join(OUT, f"heldout_{theme}.png"))


if __name__ == "__main__":
    main()
