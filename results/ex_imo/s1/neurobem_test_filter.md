Baseline: world_none. Tests are paired vs baseline; p-values only, no threshold applied.

| metric | model | mean +- std (over seeds) | n_seeds | % vs base | t-test p (n seeds) | Wilcoxon p (n seq) | seqs dropped (NaN) | warning |
|---|---|---|---|---|---|---|---|---|
| vel_RMSE | world_none (baseline) | 0.8947 +- 0.02065 | 3 | - | - | - | - |  |
| vel_RMSE | body_gyro | 1.012 +- 0.02202 | 3 | 13.2 | 0.04109 (n=3) | 0.1099 (n=13) | 0 |  |
| vel_RMSE | body_rotor | 0.8378 +- 0.00517 | 3 | -6.37 | 0.05135 (n=3) | 0.2163 (n=13) | 0 |  |
| ATE_se3 | world_none (baseline) | 2.946 +- 0.1737 | 3 | - | - | - | - |  |
| ATE_se3 | body_gyro | 3.252 +- 0.1117 | 3 | 10.4 | 0.1989 (n=3) | 0.3054 (n=13) | 0 |  |
| ATE_se3 | body_rotor | 2.725 +- 0.09721 | 3 | -7.5 | 0.05921 (n=3) | 0.4973 (n=13) | 0 |  |
| RE_T | world_none (baseline) | 2.903 +- 0.08408 | 3 | - | - | - | - |  |
| RE_T | body_gyro | 3.518 +- 0.05646 | 3 | 21.2 | 0.01336 (n=3) | 0.09424 (n=13) | 0 |  |
| RE_T | body_rotor | 2.736 +- 0.09275 | 3 | -5.76 | 0.02566 (n=3) | 0.3396 (n=13) | 0 |  |
| ATE_none | world_none (baseline) | 4.267 +- 0.3034 | 3 | - | - | - | - |  |
| ATE_none | body_gyro | 4.372 +- 0.1668 | 3 | 2.46 | 0.7284 (n=3) | 1 (n=13) | 0 |  |
| ATE_none | body_rotor | 4.871 +- 0.1845 | 3 | 14.2 | 0.04822 (n=3) | 0.7869 (n=13) | 0 |  |
| nees_median | world_none (baseline) | 0.02791 +- 0.001122 | 3 | - | - | - | - |  |
| nees_median | body_gyro | 0.03674 +- 0.0009067 | 3 | 31.6 | 0.01712 (n=3) | 0.09424 (n=13) | 0 |  |
| nees_median | body_rotor | 0.2216 +- 0.005738 | 3 | 694 | 0.0002802 (n=3) | 0.0007324 (n=13) | 0 |  |
