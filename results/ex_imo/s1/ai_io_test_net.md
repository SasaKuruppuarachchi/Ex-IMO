Baseline: world_none. Tests are paired vs baseline; p-values only, no threshold applied.

| metric | model | mean +- std (over seeds) | n_seeds | % vs base | t-test p (n seeds) | Wilcoxon p (n seq) | seqs dropped (NaN) | warning |
|---|---|---|---|---|---|---|---|---|
| RMSE | world_none (baseline) | 2.284 +- 0.02382 | 3 | - | - | - | - |  |
| RMSE | body_gyro | 2.325 +- 0.07394 | 3 | 1.8 | 0.3796 (n=3) | 0.9375 (n=7) | 0 |  |
| RMSE | body_rotor | 0.7962 +- 0.02129 | 3 | -65.1 | 0.0003002 (n=3) | 0.01562 (n=7) | 0 |  |
| AVE | world_none (baseline) | 1.868 +- 0.01192 | 3 | - | - | - | - |  |
| AVE | body_gyro | 1.89 +- 0.05061 | 3 | 1.17 | 0.56 (n=3) | 0.9375 (n=7) | 0 |  |
| AVE | body_rotor | 0.6101 +- 0.01479 | 3 | -67.3 | 7.025e-05 (n=3) | 0.01562 (n=7) | 0 |  |
