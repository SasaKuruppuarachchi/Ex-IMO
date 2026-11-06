Baseline: world_none. Tests are paired vs baseline; p-values only, no threshold applied.

| metric | model | mean +- std (over seeds) | n_seeds | % vs base | t-test p (n seeds) | Wilcoxon p (n seq) | seqs dropped (NaN) | warning |
|---|---|---|---|---|---|---|---|---|
| vel_RMSE | world_none (baseline) | 0.479 +- 0.003637 | 3 | - | - | - | - |  |
| vel_RMSE | body_gyro | 0.4577 +- 0.003494 | 3 | -4.45 | 0.02127 (n=3) | 0.0425 (n=22) | 0 |  |
| vel_RMSE | body_rotor | 0.3781 +- 0.0108 | 3 | -21.1 | 0.003985 (n=3) | 0.0009413 (n=22) | 0 |  |
| ATE_se3 | world_none (baseline) | 1.756 +- 0.04531 | 3 | - | - | - | - |  |
| ATE_se3 | body_gyro | 1.801 +- 0.04951 | 3 | 2.54 | 0.5013 (n=3) | 0.4245 (n=22) | 0 |  |
| ATE_se3 | body_rotor | 1.551 +- 0.05358 | 3 | -11.7 | 0.00514 (n=3) | 0.187 (n=22) | 0 |  |
| RE_T | world_none (baseline) | 1.773 +- 0.05759 | 3 | - | - | - | - |  |
| RE_T | body_gyro | 1.788 +- 0.05657 | 3 | 0.842 | 0.8407 (n=3) | 0.7262 (n=22) | 0 |  |
| RE_T | body_rotor | 1.541 +- 0.05861 | 3 | -13.1 | 0.001644 (n=3) | 0.1055 (n=22) | 0 |  |
| ATE_none | world_none (baseline) | 3.092 +- 0.1051 | 3 | - | - | - | - |  |
| ATE_none | body_gyro | 3.197 +- 0.1064 | 3 | 3.41 | 0.4793 (n=3) | 0.2221 (n=22) | 0 |  |
| ATE_none | body_rotor | 2.707 +- 0.1109 | 3 | -12.5 | 0.008589 (n=3) | 0.156 (n=22) | 0 |  |
| nees_median | world_none (baseline) | 12.9 +- 0.3231 | 3 | - | - | - | - |  |
| nees_median | body_gyro | 3.11 +- 0.2161 | 3 | -75.9 | 0.0009624 (n=3) | 4.768e-07 (n=22) | 0 |  |
| nees_median | body_rotor | 4.467 +- 0.4404 | 3 | -65.4 | 0.0001509 (n=3) | 9.06e-06 (n=22) | 0 |  |
