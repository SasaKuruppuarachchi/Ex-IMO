Baseline: world_none. Tests are paired vs baseline; p-values only, no threshold applied.

| metric | model | mean +- std (over seeds) | n_seeds | % vs base | t-test p (n seeds) | Wilcoxon p (n seq) | seqs dropped (NaN) | warning |
|---|---|---|---|---|---|---|---|---|
| RMSE | world_none (baseline) | 0.319 +- 0.001563 | 3 | - | - | - | - |  |
| RMSE | body_gyro | 0.3051 +- 0.005508 | 3 | -4.36 | 0.06234 (n=3) | 0.0001769 (n=22) | 0 |  |
| RMSE | body_rotor | 0.2614 +- 0.003845 | 3 | -18.1 | 0.002855 (n=3) | 0.002851 (n=22) | 0 |  |
| AVE | world_none (baseline) | 0.2499 +- 0.002255 | 3 | - | - | - | - |  |
| AVE | body_gyro | 0.2406 +- 0.007341 | 3 | -3.76 | 0.2245 (n=3) | 0.0009413 (n=22) | 0 |  |
| AVE | body_rotor | 0.2091 +- 0.005514 | 3 | -16.3 | 0.008419 (n=3) | 0.004151 (n=22) | 0 |  |
