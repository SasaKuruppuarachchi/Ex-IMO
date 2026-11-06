Baseline: world_none. Tests are paired vs baseline; p-values only, no threshold applied.

| metric | model | mean +- std (over seeds) | n_seeds | % vs base | t-test p (n seeds) | Wilcoxon p (n seq) | seqs dropped (NaN) | warning |
|---|---|---|---|---|---|---|---|---|
| vel_RMSE | world_none (baseline) | 0.7105 +- 0.1575 | 3 | - | - | - | - |  |
| vel_RMSE | body_rotor | 1.107 +- 0.007919 | 3 | 55.8 | 0.04622 (n=3) | 0.25 (n=4) | 0 |  |
| ATE_se3 | world_none (baseline) | 2.777 +- 1.091 | 3 | - | - | - | - |  |
| ATE_se3 | body_rotor | 1.42 +- 0.05916 | 3 | -48.9 | 0.1769 (n=3) | 0.25 (n=4) | 0 |  |
| RE_T | world_none (baseline) | 3.241 +- 1.317 | 3 | - | - | - | - |  |
| RE_T | body_rotor | 1.338 +- 0.06226 | 3 | -58.7 | 0.1349 (n=3) | 0.25 (n=4) | 0 |  |
