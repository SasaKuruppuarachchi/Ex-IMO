Baseline: world_none. Tests are paired vs baseline; p-values only, no threshold applied.

| metric | model | mean +- std (over seeds) | n_seeds | % vs base | t-test p (n seeds) | Wilcoxon p (n seq) | seqs dropped (NaN) | warning |
|---|---|---|---|---|---|---|---|---|
| vel_RMSE | world_none (baseline) | 0.5164 +- 0.05659 | 3 | - | - | - | - |  |
| vel_RMSE | body_gyro | 0.7731 +- 0.03554 | 3 | 49.7 | 0.002554 (n=3) | 0.03125 (n=6) | 0 |  |
| vel_RMSE | body_rotor | 0.721 +- 0.008214 | 3 | 39.6 | 0.02043 (n=3) | 0.03125 (n=6) | 0 |  |
| ATE_se3 | world_none (baseline) | 1.302 +- 0.1914 | 3 | - | - | - | - |  |
| ATE_se3 | body_gyro | 1.428 +- 0.2541 | 3 | 9.67 | 0.0889 (n=3) | 0.09375 (n=6) | 0 |  |
| ATE_se3 | body_rotor | 1.153 +- 0.07374 | 3 | -11.5 | 0.268 (n=3) | 0.5625 (n=6) | 0 |  |
| RE_T | world_none (baseline) | 1.402 +- 0.1341 | 3 | - | - | - | - |  |
| RE_T | body_gyro | 1.588 +- 0.2939 | 3 | 13.3 | 0.3005 (n=3) | 0.0625 (n=6) | 0 |  |
| RE_T | body_rotor | 1.241 +- 0.07252 | 3 | -11.5 | 0.1561 (n=3) | 0.4375 (n=6) | 0 |  |
| ATE_none | world_none (baseline) | 2.355 +- 0.5958 | 3 | - | - | - | - |  |
| ATE_none | body_gyro | 2.195 +- 0.5529 | 3 | -6.77 | 0.5203 (n=3) | 0.6875 (n=6) | 0 |  |
| ATE_none | body_rotor | 1.806 +- 0.08504 | 3 | -23.3 | 0.2224 (n=3) | 0.4375 (n=6) | 0 |  |
| nees_median | world_none (baseline) | 0.4268 +- 0.06667 | 3 | - | - | - | - |  |
| nees_median | body_gyro | 0.7802 +- 0.1023 | 3 | 82.8 | 0.003835 (n=3) | 0.09375 (n=6) | 0 |  |
| nees_median | body_rotor | 0.8863 +- 0.04874 | 3 | 108 | 0.002686 (n=3) | 0.03125 (n=6) | 0 |  |
