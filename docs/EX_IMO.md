# IMO reproduction and Ex-IMO evaluation

Status: 2026-11-06. Stages 1 and 3 done and evaluated. Stage 2 (attribution: world frame + torque, body frame without torque) in progress.

All results use `data/clean`, so they aren't directly comparable with published numbers on the original files.

## Models

| name | frame | input | output |
|---|---|---|---|
| A, base IMO | world | R ω, R T | Δp in world |
| B, Ex-IMO | body | ω, T + Rᵀg, τ | Δp in body frame at window start |
| variants for attribution | body with no τ; world with τ; body with rotor τ | | |

Filter update: `h = p_j − p_i` (world) or `h = R_iᵀ(p_j − p_i)` (body), Jacobian checked numerically (`tests/test_filter_ex.py`).

## Decisions where the spec conflicts or can't be followed literally

1. **T_b is not computed from the spec's inverse-dynamics formula.** `T = 2Rᵀ(Δp/Δt² − v/Δt − g)` uses the network's own target Δp and the true velocity. As an input it would leak the label and can't be computed at inference. T comes from rotor signals; inverse dynamics is only the fitting target on the training split.
2. **Input frame.** Spec section 3A rotates all inputs to world; 2D and 4.2 require Ex-IMO in body frame. Model A follows 3A and model B follows 2D.
3. **τ source.** The spec's `Jω̇ + ω×Jω` is a function of the gyro history the network already sees, so it adds no information in principle (only a useful transform). Rotor-derived torque does add information, so it is tested as a variant.
4. **J is unknown on three platforms.** τ is normalised by J (rad/s²), so only inertia ratios enter, as the spec's alternative allows.
5. **Splits.** Fixed shape-based splits (`data_prep/public_uav.py`) are used, not a new 70/15/15. AI-IO's split already has that shape (manual 70/15/15, patterned flights never trained on).
6. **Same training for A and B:** MSE, Gaussian noise on orientation (2°) and gyro bias (0.005 rad/s) as in the spec, 50-step target, same seeds.

## Upstream problems found

| problem | evidence | handling |
|---|---|---|
| Target spans 49 steps but the filter treats it as 50 (0.49 vs 0.50 s) | shipped checkpoint: scale 1.00 vs 49-step displacement, 0.98 vs 50-step (train split) | target uses 50 steps for all new models |
| `int(t * 1e6)` truncates timestamps; one interpolated sample per IMU message | crashes on NanoBench and NeuroBEM | `round`, `while` over gaps |
| `scheduler` is created but never stepped; no seeding; validation on one random sequence | code reading | no scheduler for A or B, seeded, whole validation set |

Baseline check: shipped checkpoint, shipped Blackbird clip (clover test, 30 s), default filter: ATE 0.38 m, velocity RMSE 0.47 m/s, median NEES 632. This is one clip, and it has not been compared with the paper's numbers. Full Blackbird and DIDO are not in this workspace.

## Physics fits (training split; validation shown)

| dataset | signal | thrust map | delay | R² vs inverse dynamics | RMSE m/s² | accelerometer ratio | allocation R² (x, y, z) |
|---|---|---|---|---|---|---|---|
| AI-IO | rotor speed | a u² + b u | 0 | 0.84 | 0.94 | 1.017 | 0.39, 0.07, 0.08 |
| NanoBench | PWM | a u² + b u | 50 ms | 0.15 | 0.30 | 0.993 | 0.04, 0.13, 0.02 |
| TII-RATM | command | a u² + b u, with vbat | 0 | 0.90 | 2.87 | 0.986 | 0.19, 0.10, 0.46 |
| NeuroBEM | rotor speed | a u² + b u | 0 | 0.95 | 1.72 | 0.996 | 0.20, 0.15, 0.07 |

- NanoBench's low R² reflects near-constant thrust on gentle flights; its RMSE is small.
- Allocation signs recover NeuroBEM's documented motor layout with no prior knowledge.
- **Allocation R² is low.** On NeuroBEM the gains are also about 5× below a rough estimate with an assumed 0.08 m lever arm (the arm length is undocumented). Rotor differentials explain only part of ω̇ at these bandwidths, so `tau_rotor` is a rotor-differential feature, not true torque.
- Rotors lead the body response by 20–50 ms on the datasets logging commands (NanoBench, TII x/y) and by ≈0 on those logging measured speed (`scripts/diag/rotor_gyro_lag.py`).
- Fitted inertia ratios were unreliable (wrong sign on NeuroBEM against the published J), so NeuroBEM uses its published J and the others assume c = [0.8, −0.8, 0].

Assumptions: thrust is mass-normalised and fitted, so mass and kf are not needed separately. Masses are documented only for NanoBench (0.04085 kg) and NeuroBEM (Readme 0.772 kg, paper 0.752 kg). Rotor signals at 100 Hz, decimated without an anti-alias filter as in M4.

## Known caveats

- The body-frame update makes heading appear observable through the current-estimate Jacobian, which can make the filter over-confident in yaw. No first-estimate Jacobian is used yet; check heading NEES on real runs.
- The network input uses offline gyro calibration, as upstream, which is zero on these datasets. The filter's bias estimate is not subtracted, unlike what spec 3A says, because training data has no bias removed either.
- Network AVE and RMSE are errors of the mean velocity over 0.5 s, not AI-IO's instantaneous velocity over 1 s; the filter's `vel_RMSE` is the same quantity as AI-IO's. `RE_T` (rpg definition) differs from AI-IO's `position_rrmse`; both are reported.

## Stage 1 results (3 seeds, best-validation checkpoint, filter tuned on validation)

Baseline is base IMO (world frame, no torque). % change vs baseline; p from a paired t-test across seeds (n = 3) and a
Wilcoxon test across sequences. Both Ex-IMO variants are body frame. Full tables, with ATE_none and NEES:
`results/ex_imo/s1/` (also the filter settings chosen on validation, `selection_<dataset>.json`).

Filter velocity RMSE [m/s] and ATE after SE(3) alignment [m]:

| dataset, split | base IMO vel / ATE | Ex-IMO gyro τ vel / ATE | Ex-IMO rotor τ vel / ATE |
|---|---|---|---|
| TII test | **0.516** / 1.30 | 0.773 (+50%) / 1.43 (+10%) | 0.721 (+40%, p 0.02) / **1.15** (−12%, p 0.27) |
| NanoBench test | 0.479 / 1.76 | 0.458 (−4%) / 1.80 (+3%) | **0.378** (−21%, p 0.004) / **1.55** (−12%, p 0.005) |
| NeuroBEM test | 0.895 / 2.95 | 1.012 (+13%) / 3.25 (+10%) | **0.838** (−6%, p 0.05) / **2.73** (−8%, p 0.06) |
| AI-IO test | 1.384 / 4.32 | 1.420 (+3%) / 5.24 (+21%) | **0.519** (−63%, p 3e-4) / **1.21** (−72%, p 1e-3) |
| AI-IO unseen (patterned) | 1.082 / 14.6 | 1.114 (+3%) / 5.96 (−59%) | **0.461** (−57%, p 8e-4) / **2.90** (−80%, p 1e-3) |

Network alone, RMSE of the mean velocity over the 0.5 s window [m/s]: TII 0.186 / 0.286 / 0.312; NanoBench 0.319 /
0.305 / 0.261; NeuroBEM 1.308 / 1.618 / 0.967; AI-IO test 2.284 / 2.325 / 0.796; AI-IO unseen 1.305 / 1.399 / 0.401.

Findings:
- **Ex-IMO as specified (gyro-derived τ) is not better than base IMO** on any dataset's velocity, and worse on TII and
  NeuroBEM. Its one large gain, AI-IO unseen ATE −59%, is a heading effect: the world-frame model's error grows on
  flights whose headings it never saw (see the yaw test below), and body frame removes that.
- **Ex-IMO with rotor-derived τ is better on three of four datasets, and by a lot on AI-IO**, including the unseen
  patterned flights (−57% velocity, −80% ATE). On TII it loses on velocity and wins on ATE.
- **The rotor gain is velocity information, not torque** (`scripts/diag/rotor_gain_check.py`, validation only): ridge
  regression from rotor τ alone explains body-frame x/y displacement with R² 0.94/0.71 (AI-IO) and 0.80/0.78 (NeuroBEM);
  gyro τ explains ~0. Swapping τ between windows of a flight or delaying it by 1 s removes the gain. Likely cause, not
  verified: the rotors trim against aerodynamic moments that grow with airspeed. Indoor data only; wind would decouple
  airspeed from ground speed.
- **Base IMO memorises track headings on TII:** rotating the flights 90° in yaw raises its validation error from
  0.34 to 5.8 m/s (`scripts/eval_net.py --world_yaw_deg 90`, validation, seed 42); body-frame models don't change. TII's train, val and test fly the same tracks, so stage 1 rewards it.
  Stage 3 tests this directly.
- **Filter weight on the network:** on AI-IO and NeuroBEM, base IMO and gyro-τ chose the largest measurement noise in
  the grid (`const_cov` 10, after two extensions); rotor-τ chose interior settings. The filter trusts the weaker
  networks little there. Filter NEES medians are far below 2.37 (over-cautious) for those settings.
- **Mocap glitch fix** (AI-IO seed 42): validation changed by 1–4% (1.358 → 1.343, 1.240 → 1.227, 0.396 → 0.380 m).

## Stage 3: held-out shapes, defined before any result

Each fold removes one group of shapes from train and val and from the thrust and torque fits (`--folds` in the converter), and
evaluates on all of that group's flights, whatever their original split (`unseen.txt`). Remaining test flights stay in `test.txt`, so the seen/unseen gap is visible in one model.

| dataset | fold | shapes held out |
|---|---|---|
| TII | ellipse, lemniscate, trackRATM | one track type each |
| NanoBench | crossing | figure-8, star, trefoil |
| NanoBench | round | circle, oval, helix |
| NeuroBEM | circles | every flight whose `Flights.txt` comment contains circle or ellipse |
| NeuroBEM | lemniscate_cpc | lemniscate and time-optimal (cpc) flights |

Runs: base IMO (world) against Ex-IMO (body) x 3 seeds = 42. Ex-IMO's torque source per dataset is stage 1's validation choice (rotor on all three). Filter settings are tuned per fold on that fold's validation flights. AI-IO has no folds: its patterned flights already play this part in stage 1.

### Stage 3 results (3 seeds; filter tuned on each fold's validation flights; held-out = all flights of the held-out shapes)

Base IMO → Ex-IMO (rotor τ), filter velocity RMSE [m/s] and ATE_se3 [m]; p from a paired t-test across seeds.

| held-out shapes | vel_RMSE | ATE_se3 | network RMSE |
|---|---|---|---|
| TII ellipse | 5.73 → 2.19 (−62%, p 0.04) | 4.97 → 8.44 (+70%, p 0.03) | 3.48 → 3.96 (+14%) |
| TII lemniscate | 6.55 → 1.84 (−72%, p 0.001) | 10.4 → 9.61 (−8%, p 0.25) | 4.29 → 3.14 (−27%) |
| TII trackRATM | 8.46 → 4.81 (−43%, p 0.01) | 16.9 → 20.0 (+18%, p 0.27) | 5.96 → 4.95 (−17%) |
| NanoBench crossing | 0.609 → 0.569 (−6%, p 0.10) | 1.93 → 1.81 (−6%, p 0.28) | 0.419 → 0.399 (−5%) |
| NanoBench round | 0.557 → 0.471 (−16%, p 0.006) | 1.33 → 1.63 (+23%, p 0.08) | 0.408 → 0.349 (−15%) |
| NeuroBEM circles | 0.777 → 0.522 (−33%, p 0.002) | 2.39 → 1.21 (−50%, p 0.003) | 1.346 → 0.809 (−40%) |
| NeuroBEM lemniscate + cpc | 1.111 → 0.718 (−35%, p 0.005) | 4.11 → 2.76 (−33%, p 0.03) | 2.082 → 1.243 (−40%) |

Seen-shape test flights of the same models: `results/ex_imo/s3/`.

- **Velocity: Ex-IMO is better on held-out shapes in 7/7 folds** (6 with p < 0.05 across seeds).
- **Position: better in 4/7, worse in 3/7** (TII ellipse significantly). Not explained yet; a slow heading drift in the
  body-frame update is one candidate, unchecked.
- **TII doesn't generalise across tracks for either model**: network error on held-out tracks is 3–6 m/s against
  0.1–0.35 m/s on seen ones, from 6 training flights of 2 track types. Its % changes carry little weight.
- **NeuroBEM is the clean case**: many flights per fold, both models trained well, and Ex-IMO wins every metric.
- Filter settings at the grid edge again for base IMO on both NeuroBEM folds (const_cov 10, sigma_na 30) and for
  Ex-IMO on TII trackRATM (sigma_na 30).

Verdict on step 4 ("Ex-IMO outperforms base IMO on unseen trajectories"), for this data: **true for velocity in all
folds and for position on NeuroBEM and AI-IO's patterned flights, not for position on TII or NanoBench round. Only with
rotor-derived τ:** the spec's gyro-derived τ gave no gain in stage 1, so it wasn't run in stage 3. Stage 2 is meant to
separate how much comes from the body frame and how much from rotor τ.
