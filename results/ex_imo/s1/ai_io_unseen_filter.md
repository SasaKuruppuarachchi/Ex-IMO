Baseline: world_none. Tests are paired vs baseline; p-values only, no threshold applied.

| metric | model | mean +- std (over seeds) | n_seeds | % vs base | t-test p (n seeds) | Wilcoxon p (n seq) | seqs dropped (NaN) | warning |
|---|---|---|---|---|---|---|---|---|
| vel_RMSE | world_none (baseline) | 1.082 +- 0.04627 | 3 | - | - | - | - |  |
| vel_RMSE | body_gyro | 1.114 +- 0.0282 | 3 | 3.01 | 0.4318 (n=3) | 0.8311 (n=11) | 0 |  |
| vel_RMSE | body_rotor | 0.4605 +- 0.01819 | 3 | -57.4 | 0.0008065 (n=3) | 0.0009766 (n=11) | 0 |  |
| ATE_se3 | world_none (baseline) | 14.57 +- 1.081 | 3 | - | - | - | - |  |
| ATE_se3 | body_gyro | 5.957 +- 1.5 | 3 | -59.1 | 0.004222 (n=3) | 0.00293 (n=11) | 0 |  |
| ATE_se3 | body_rotor | 2.897 +- 0.337 | 3 | -80.1 | 0.001492 (n=3) | 0.0009766 (n=11) | 0 |  |
| RE_T | world_none (baseline) | 14.34 +- 1.021 | 3 | - | - | - | - |  |
| RE_T | body_gyro | 6.611 +- 1.306 | 3 | -53.9 | 0.003777 (n=3) | 0.00293 (n=11) | 0 |  |
| RE_T | body_rotor | 2.927 +- 0.3433 | 3 | -79.6 | 0.00135 (n=3) | 0.0009766 (n=11) | 0 |  |
| ATE_none | world_none (baseline) | 30.58 +- 2.025 | 3 | - | - | - | - |  |
| ATE_none | body_gyro | 11.28 +- 2.408 | 3 | -63.1 | 0.00323 (n=3) | 0.00293 (n=11) | 0 |  |
| ATE_none | body_rotor | 5.737 +- 0.7181 | 3 | -81.2 | 0.0009773 (n=3) | 0.0009766 (n=11) | 0 |  |
| nees_median | world_none (baseline) | 0.03758 +- 0.003771 | 3 | - | - | - | - |  |
| nees_median | body_gyro | 0.03559 +- 0.002157 | 3 | -5.3 | 0.5344 (n=3) | 0.9658 (n=11) | 0 |  |
| nees_median | body_rotor | 0.1134 +- 0.006967 | 3 | 202 | 0.0009662 (n=3) | 0.001953 (n=11) | 0 |  |
