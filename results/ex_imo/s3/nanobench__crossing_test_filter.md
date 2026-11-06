Baseline: world_none. Tests are paired vs baseline; p-values only, no threshold applied.

| metric | model | mean +- std (over seeds) | n_seeds | % vs base | t-test p (n seeds) | Wilcoxon p (n seq) | seqs dropped (NaN) | warning |
|---|---|---|---|---|---|---|---|---|
| vel_RMSE | world_none (baseline) | 0.4443 +- 0.002496 | 3 | - | - | - | - |  |
| vel_RMSE | body_rotor | 0.4057 +- 0.006765 | 3 | -8.67 | 0.01115 (n=3) | 0.3054 (n=13) | 0 |  |
| ATE_se3 | world_none (baseline) | 1.9 +- 0.0412 | 3 | - | - | - | - |  |
| ATE_se3 | body_rotor | 1.778 +- 0.1313 | 3 | -6.4 | 0.1848 (n=3) | 0.8394 (n=13) | 0 |  |
| RE_T | world_none (baseline) | 1.952 +- 0.03538 | 3 | - | - | - | - |  |
| RE_T | body_rotor | 1.837 +- 0.1229 | 3 | -5.9 | 0.1702 (n=3) | 0.946 (n=13) | 0 |  |
