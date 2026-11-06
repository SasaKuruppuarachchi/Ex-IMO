Baseline: world_none. Tests are paired vs baseline; p-values only, no threshold applied.

| metric | model | mean +- std (over seeds) | n_seeds | % vs base | t-test p (n seeds) | Wilcoxon p (n seq) | seqs dropped (NaN) | warning |
|---|---|---|---|---|---|---|---|---|
| RMSE | world_none (baseline) | 1.305 +- 0.06166 | 3 | - | - | - | - |  |
| RMSE | body_gyro | 1.399 +- 0.04946 | 3 | 7.17 | 0.06743 (n=3) | 0.1748 (n=11) | 0 |  |
| RMSE | body_rotor | 0.4009 +- 0.04191 | 3 | -69.3 | 0.0007249 (n=3) | 0.0009766 (n=11) | 0 |  |
| AVE | world_none (baseline) | 1.191 +- 0.05427 | 3 | - | - | - | - |  |
| AVE | body_gyro | 1.184 +- 0.04644 | 3 | -0.618 | 0.8265 (n=3) | 0.7646 (n=11) | 0 |  |
| AVE | body_rotor | 0.3617 +- 0.03875 | 3 | -69.6 | 0.0004367 (n=3) | 0.0009766 (n=11) | 0 |  |
