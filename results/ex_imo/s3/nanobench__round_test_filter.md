Baseline: world_none. Tests are paired vs baseline; p-values only, no threshold applied.

| metric | model | mean +- std (over seeds) | n_seeds | % vs base | t-test p (n seeds) | Wilcoxon p (n seq) | seqs dropped (NaN) | warning |
|---|---|---|---|---|---|---|---|---|
| vel_RMSE | world_none (baseline) | 0.4721 +- 0.004726 | 3 | - | - | - | - |  |
| vel_RMSE | body_rotor | 0.4278 +- 0.003456 | 3 | -9.38 | 0.01113 (n=3) | 0.1677 (n=13) | 0 |  |
| ATE_se3 | world_none (baseline) | 1.414 +- 0.04063 | 3 | - | - | - | - |  |
| ATE_se3 | body_rotor | 1.452 +- 0.07447 | 3 | 2.68 | 0.5998 (n=3) | 0.8394 (n=13) | 0 |  |
| RE_T | world_none (baseline) | 1.483 +- 0.03973 | 3 | - | - | - | - |  |
| RE_T | body_rotor | 1.515 +- 0.09513 | 3 | 2.13 | 0.7036 (n=3) | 0.7869 (n=13) | 0 |  |
