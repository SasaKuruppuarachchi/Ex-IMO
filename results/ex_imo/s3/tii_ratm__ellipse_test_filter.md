Baseline: world_none. Tests are paired vs baseline; p-values only, no threshold applied.

| metric | model | mean +- std (over seeds) | n_seeds | % vs base | t-test p (n seeds) | Wilcoxon p (n seq) | seqs dropped (NaN) | warning |
|---|---|---|---|---|---|---|---|---|
| vel_RMSE | world_none (baseline) | 0.5449 +- 0.00802 | 3 | - | - | - | - |  |
| vel_RMSE | body_rotor | 0.9748 +- 0.01437 | 3 | 78.9 | 0.0001172 (n=3) | 0.125 (n=4) | 0 |  |
| ATE_se3 | world_none (baseline) | 1.67 +- 0.1802 | 3 | - | - | - | - |  |
| ATE_se3 | body_rotor | 1.416 +- 0.2084 | 3 | -15.2 | 0.2804 (n=3) | 0.875 (n=4) | 0 |  |
| RE_T | world_none (baseline) | 1.917 +- 0.2158 | 3 | - | - | - | - |  |
| RE_T | body_rotor | 1.415 +- 0.1963 | 3 | -26.2 | 0.08371 (n=3) | 0.875 (n=4) | 0 |  |
