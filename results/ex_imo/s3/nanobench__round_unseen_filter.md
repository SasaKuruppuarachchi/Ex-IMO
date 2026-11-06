Baseline: world_none. Tests are paired vs baseline; p-values only, no threshold applied.

| metric | model | mean +- std (over seeds) | n_seeds | % vs base | t-test p (n seeds) | Wilcoxon p (n seq) | seqs dropped (NaN) | warning |
|---|---|---|---|---|---|---|---|---|
| vel_RMSE | world_none (baseline) | 0.5569 +- 0.007313 | 3 | - | - | - | - |  |
| vel_RMSE | body_rotor | 0.4705 +- 0.008014 | 3 | -15.5 | 0.005645 (n=3) | 2.041e-06 (n=27) | 0 |  |
| ATE_se3 | world_none (baseline) | 1.325 +- 0.01384 | 3 | - | - | - | - |  |
| ATE_se3 | body_rotor | 1.634 +- 0.1561 | 3 | 23.3 | 0.07885 (n=3) | 0.01208 (n=27) | 0 |  |
| RE_T | world_none (baseline) | 1.436 +- 0.0051 | 3 | - | - | - | - |  |
| RE_T | body_rotor | 1.668 +- 0.1343 | 3 | 16.1 | 0.09139 (n=3) | 0.04626 (n=27) | 0 |  |
