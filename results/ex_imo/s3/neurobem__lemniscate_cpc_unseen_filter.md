Baseline: world_none. Tests are paired vs baseline; p-values only, no threshold applied.

| metric | model | mean +- std (over seeds) | n_seeds | % vs base | t-test p (n seeds) | Wilcoxon p (n seq) | seqs dropped (NaN) | warning |
|---|---|---|---|---|---|---|---|---|
| vel_RMSE | world_none (baseline) | 1.111 +- 0.03554 | 3 | - | - | - | - |  |
| vel_RMSE | body_rotor | 0.7181 +- 0.01734 | 3 | -35.4 | 0.004543 (n=3) | 5.122e-10 (n=62) | 0 |  |
| ATE_se3 | world_none (baseline) | 4.114 +- 0.3863 | 3 | - | - | - | - |  |
| ATE_se3 | body_rotor | 2.759 +- 0.1492 | 3 | -32.9 | 0.03459 (n=3) | 1.235e-05 (n=62) | 0 |  |
| RE_T | world_none (baseline) | 4.37 +- 0.3149 | 3 | - | - | - | - |  |
| RE_T | body_rotor | 2.821 +- 0.1212 | 3 | -35.4 | 0.01767 (n=3) | 5.633e-08 (n=62) | 0 |  |
