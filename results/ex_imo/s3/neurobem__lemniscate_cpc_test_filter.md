Baseline: world_none. Tests are paired vs baseline; p-values only, no threshold applied.

| metric | model | mean +- std (over seeds) | n_seeds | % vs base | t-test p (n seeds) | Wilcoxon p (n seq) | seqs dropped (NaN) | warning |
|---|---|---|---|---|---|---|---|---|
| vel_RMSE | world_none (baseline) | 0.9248 +- 0.02772 | 3 | - | - | - | - |  |
| vel_RMSE | body_rotor | 0.8085 +- 0.00964 | 3 | -12.6 | 0.008509 (n=3) | 0.2969 (n=7) | 0 |  |
| ATE_se3 | world_none (baseline) | 3.02 +- 0.2753 | 3 | - | - | - | - |  |
| ATE_se3 | body_rotor | 2.442 +- 0.0516 | 3 | -19.1 | 0.08704 (n=3) | 0.2188 (n=7) | 0 |  |
| RE_T | world_none (baseline) | 2.844 +- 0.3138 | 3 | - | - | - | - |  |
| RE_T | body_rotor | 2.586 +- 0.07266 | 3 | -9.09 | 0.3137 (n=3) | 0.8125 (n=7) | 0 |  |
