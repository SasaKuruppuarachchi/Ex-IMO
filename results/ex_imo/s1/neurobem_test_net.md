Baseline: world_none. Tests are paired vs baseline; p-values only, no threshold applied.

| metric | model | mean +- std (over seeds) | n_seeds | % vs base | t-test p (n seeds) | Wilcoxon p (n seq) | seqs dropped (NaN) | warning |
|---|---|---|---|---|---|---|---|---|
| RMSE | world_none (baseline) | 1.308 +- 0.04526 | 3 | - | - | - | - |  |
| RMSE | body_gyro | 1.618 +- 0.02629 | 3 | 23.7 | 0.01703 (n=3) | 0.02661 (n=13) | 0 |  |
| RMSE | body_rotor | 0.9674 +- 0.0131 | 3 | -26 | 0.009652 (n=3) | 0.02148 (n=13) | 0 |  |
| AVE | world_none (baseline) | 1.112 +- 0.04569 | 3 | - | - | - | - |  |
| AVE | body_gyro | 1.376 +- 0.02476 | 3 | 23.8 | 0.02233 (n=3) | 0.01709 (n=13) | 0 |  |
| AVE | body_rotor | 0.7844 +- 0.01505 | 3 | -29.5 | 0.01123 (n=3) | 0.02661 (n=13) | 0 |  |
