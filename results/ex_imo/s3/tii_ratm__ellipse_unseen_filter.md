Baseline: world_none. Tests are paired vs baseline; p-values only, no threshold applied.

| metric | model | mean +- std (over seeds) | n_seeds | % vs base | t-test p (n seeds) | Wilcoxon p (n seq) | seqs dropped (NaN) | warning |
|---|---|---|---|---|---|---|---|---|
| vel_RMSE | world_none (baseline) | 5.728 +- 1.215 | 3 | - | - | - | - |  |
| vel_RMSE | body_rotor | 2.185 +- 0.01455 | 3 | -61.8 | 0.03733 (n=3) | 0.03125 (n=6) | 0 |  |
| ATE_se3 | world_none (baseline) | 4.965 +- 1.334 | 3 | - | - | - | - |  |
| ATE_se3 | body_rotor | 8.436 +- 0.2393 | 3 | 69.9 | 0.03161 (n=3) | 0.03125 (n=6) | 0 |  |
| RE_T | world_none (baseline) | 6.823 +- 0.8881 | 3 | - | - | - | - |  |
| RE_T | body_rotor | 8.172 +- 0.4022 | 3 | 19.8 | 0.04782 (n=3) | 0.03125 (n=6) | 0 |  |
