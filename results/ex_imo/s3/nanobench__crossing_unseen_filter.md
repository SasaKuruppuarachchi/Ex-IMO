Baseline: world_none. Tests are paired vs baseline; p-values only, no threshold applied.

| metric | model | mean +- std (over seeds) | n_seeds | % vs base | t-test p (n seeds) | Wilcoxon p (n seq) | seqs dropped (NaN) | warning |
|---|---|---|---|---|---|---|---|---|
| vel_RMSE | world_none (baseline) | 0.6086 +- 0.003236 | 3 | - | - | - | - |  |
| vel_RMSE | body_rotor | 0.5693 +- 0.02564 | 3 | -6.44 | 0.1018 (n=3) | 0.1668 (n=46) | 0 |  |
| ATE_se3 | world_none (baseline) | 1.928 +- 0.0406 | 3 | - | - | - | - |  |
| ATE_se3 | body_rotor | 1.806 +- 0.1551 | 3 | -6.33 | 0.2841 (n=3) | 0.6571 (n=46) | 0 |  |
| RE_T | world_none (baseline) | 2.023 +- 0.03548 | 3 | - | - | - | - |  |
| RE_T | body_rotor | 1.841 +- 0.1318 | 3 | -8.98 | 0.1451 (n=3) | 0.2873 (n=46) | 0 |  |
