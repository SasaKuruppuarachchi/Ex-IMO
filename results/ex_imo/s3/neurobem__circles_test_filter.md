Baseline: world_none. Tests are paired vs baseline; p-values only, no threshold applied.

| metric | model | mean +- std (over seeds) | n_seeds | % vs base | t-test p (n seeds) | Wilcoxon p (n seq) | seqs dropped (NaN) | warning |
|---|---|---|---|---|---|---|---|---|
| vel_RMSE | world_none (baseline) | 0.8846 +- 0.0114 | 3 | - | - | - | - |  |
| vel_RMSE | body_rotor | 0.706 +- 0.01707 | 3 | -20.2 | 0.006595 (n=3) | 0.7695 (n=10) | 0 |  |
| ATE_se3 | world_none (baseline) | 3.392 +- 0.3779 | 3 | - | - | - | - |  |
| ATE_se3 | body_rotor | 3.066 +- 0.1699 | 3 | -9.59 | 0.3413 (n=3) | 0.5566 (n=10) | 0 |  |
| RE_T | world_none (baseline) | 3.497 +- 0.1778 | 3 | - | - | - | - |  |
| RE_T | body_rotor | 3.038 +- 0.113 | 3 | -13.1 | 0.03482 (n=3) | 0.4316 (n=10) | 0 |  |
