Baseline: world_none. Tests are paired vs baseline; p-values only, no threshold applied.

| metric | model | mean +- std (over seeds) | n_seeds | % vs base | t-test p (n seeds) | Wilcoxon p (n seq) | seqs dropped (NaN) | warning |
|---|---|---|---|---|---|---|---|---|
| vel_RMSE | world_none (baseline) | 1.384 +- 0.02227 | 3 | - | - | - | - |  |
| vel_RMSE | body_gyro | 1.42 +- 0.05173 | 3 | 2.63 | 0.4671 (n=3) | 0.9375 (n=7) | 0 |  |
| vel_RMSE | body_rotor | 0.5188 +- 0.001919 | 3 | -62.5 | 0.0002579 (n=3) | 0.03125 (n=7) | 0 |  |
| ATE_se3 | world_none (baseline) | 4.322 +- 0.1998 | 3 | - | - | - | - |  |
| ATE_se3 | body_gyro | 5.244 +- 0.1829 | 3 | 21.3 | 0.02264 (n=3) | 0.2969 (n=7) | 0 |  |
| ATE_se3 | body_rotor | 1.206 +- 0.0351 | 3 | -72.1 | 0.0009649 (n=3) | 0.01562 (n=7) | 0 |  |
| RE_T | world_none (baseline) | 4.874 +- 0.0905 | 3 | - | - | - | - |  |
| RE_T | body_gyro | 5.856 +- 0.2101 | 3 | 20.1 | 0.02899 (n=3) | 0.375 (n=7) | 0 |  |
| RE_T | body_rotor | 1.538 +- 0.03052 | 3 | -68.5 | 0.0004157 (n=3) | 0.01562 (n=7) | 0 |  |
| ATE_none | world_none (baseline) | 6.251 +- 0.2869 | 3 | - | - | - | - |  |
| ATE_none | body_gyro | 7.715 +- 0.1619 | 3 | 23.4 | 0.02588 (n=3) | 0.2188 (n=7) | 0 |  |
| ATE_none | body_rotor | 2.462 +- 0.06914 | 3 | -60.6 | 0.002226 (n=3) | 0.03125 (n=7) | 0 |  |
| nees_median | world_none (baseline) | 0.05495 +- 0.003124 | 3 | - | - | - | - |  |
| nees_median | body_gyro | 0.05247 +- 0.003705 | 3 | -4.51 | 0.5053 (n=3) | 0.8125 (n=7) | 0 |  |
| nees_median | body_rotor | 0.1065 +- 0.001082 | 3 | 93.8 | 0.002118 (n=3) | 0.01562 (n=7) | 0 |  |
