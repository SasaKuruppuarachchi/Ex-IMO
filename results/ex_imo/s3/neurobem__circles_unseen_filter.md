Baseline: world_none. Tests are paired vs baseline; p-values only, no threshold applied.

| metric | model | mean +- std (over seeds) | n_seeds | % vs base | t-test p (n seeds) | Wilcoxon p (n seq) | seqs dropped (NaN) | warning |
|---|---|---|---|---|---|---|---|---|
| vel_RMSE | world_none (baseline) | 0.7767 +- 0.02245 | 3 | - | - | - | - |  |
| vel_RMSE | body_rotor | 0.5217 +- 0.005914 | 3 | -32.8 | 0.002053 (n=3) | 1.519e-08 (n=84) | 0 |  |
| ATE_se3 | world_none (baseline) | 2.389 +- 0.09267 | 3 | - | - | - | - |  |
| ATE_se3 | body_rotor | 1.205 +- 0.01685 | 3 | -49.6 | 0.002824 (n=3) | 1.939e-09 (n=84) | 0 |  |
| RE_T | world_none (baseline) | 2.26 +- 0.06947 | 3 | - | - | - | - |  |
| RE_T | body_rotor | 1.275 +- 0.02606 | 3 | -43.6 | 0.002955 (n=3) | 2.14e-07 (n=84) | 0 |  |
