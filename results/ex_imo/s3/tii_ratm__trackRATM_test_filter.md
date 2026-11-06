Baseline: world_none. Tests are paired vs baseline; p-values only, no threshold applied.

| metric | model | mean +- std (over seeds) | n_seeds | % vs base | t-test p (n seeds) | Wilcoxon p (n seq) | seqs dropped (NaN) | warning |
|---|---|---|---|---|---|---|---|---|
| vel_RMSE | world_none (baseline) | 0.3185 +- 0.009388 | 3 | - | - | - | - |  |
| vel_RMSE | body_rotor | 0.4845 +- 0.01151 | 3 | 52.1 | 0.004697 (n=3) | 0.125 (n=4) | 0 |  |
| ATE_se3 | world_none (baseline) | 0.2268 +- 0.05061 | 3 | - | - | - | - |  |
| ATE_se3 | body_rotor | 0.6884 +- 0.009778 | 3 | 204 | 0.004989 (n=3) | 0.125 (n=4) | 0 |  |
| RE_T | world_none (baseline) | 0.428 +- 0.03832 | 3 | - | - | - | - |  |
| RE_T | body_rotor | 0.623 +- 0.00674 | 3 | 45.5 | 0.01727 (n=3) | 0.125 (n=4) | 0 |  |
