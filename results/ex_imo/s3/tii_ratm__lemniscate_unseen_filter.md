Baseline: world_none. Tests are paired vs baseline; p-values only, no threshold applied.

| metric | model | mean +- std (over seeds) | n_seeds | % vs base | t-test p (n seeds) | Wilcoxon p (n seq) | seqs dropped (NaN) | warning |
|---|---|---|---|---|---|---|---|---|
| vel_RMSE | world_none (baseline) | 6.547 +- 0.302 | 3 | - | - | - | - |  |
| vel_RMSE | body_rotor | 1.836 +- 0.06489 | 3 | -72 | 0.001294 (n=3) | 0.03125 (n=6) | 0 |  |
| ATE_se3 | world_none (baseline) | 10.43 +- 0.5814 | 3 | - | - | - | - |  |
| ATE_se3 | body_rotor | 9.613 +- 0.3831 | 3 | -7.82 | 0.2493 (n=3) | 1 (n=6) | 0 |  |
| RE_T | world_none (baseline) | 8.855 +- 0.3071 | 3 | - | - | - | - |  |
| RE_T | body_rotor | 6.736 +- 0.464 | 3 | -23.9 | 0.03619 (n=3) | 0.03125 (n=6) | 0 |  |
