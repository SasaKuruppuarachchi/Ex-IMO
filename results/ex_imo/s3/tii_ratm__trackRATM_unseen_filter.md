Baseline: world_none. Tests are paired vs baseline; p-values only, no threshold applied.

| metric | model | mean +- std (over seeds) | n_seeds | % vs base | t-test p (n seeds) | Wilcoxon p (n seq) | seqs dropped (NaN) | warning |
|---|---|---|---|---|---|---|---|---|
| vel_RMSE | world_none (baseline) | 8.456 +- 0.6945 | 3 | - | - | - | - |  |
| vel_RMSE | body_rotor | 4.808 +- 0.08139 | 3 | -43.1 | 0.01268 (n=3) | 0.03125 (n=6) | 0 |  |
| ATE_se3 | world_none (baseline) | 16.89 +- 2.408 | 3 | - | - | - | - |  |
| ATE_se3 | body_rotor | 20 +- 1.205 | 3 | 18.5 | 0.2735 (n=3) | 0.0625 (n=6) | 0 |  |
| RE_T | world_none (baseline) | 14.93 +- 1.061 | 3 | - | - | - | - |  |
| RE_T | body_rotor | 17.4 +- 0.6545 | 3 | 16.6 | 0.1299 (n=3) | 0.0625 (n=6) | 0 |  |
