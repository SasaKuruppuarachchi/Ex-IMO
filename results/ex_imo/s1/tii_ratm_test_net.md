Baseline: world_none. Tests are paired vs baseline; p-values only, no threshold applied.

| metric | model | mean +- std (over seeds) | n_seeds | % vs base | t-test p (n seeds) | Wilcoxon p (n seq) | seqs dropped (NaN) | warning |
|---|---|---|---|---|---|---|---|---|
| RMSE | world_none (baseline) | 0.1862 +- 0.009033 | 3 | - | - | - | - |  |
| RMSE | body_gyro | 0.2856 +- 0.01713 | 3 | 53.4 | 0.005725 (n=3) | 0.03125 (n=6) | 0 |  |
| RMSE | body_rotor | 0.3122 +- 0.01302 | 3 | 67.6 | 0.01005 (n=3) | 0.03125 (n=6) | 0 |  |
| AVE | world_none (baseline) | 0.1437 +- 0.007129 | 3 | - | - | - | - |  |
| AVE | body_gyro | 0.1991 +- 0.0145 | 3 | 38.5 | 0.01784 (n=3) | 0.03125 (n=6) | 0 |  |
| AVE | body_rotor | 0.2144 +- 0.01441 | 3 | 49.1 | 0.02947 (n=3) | 0.03125 (n=6) | 0 |  |
