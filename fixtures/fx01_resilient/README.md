# Replication package: "AI adoption and firm performance" (synthetic study)

## Contents
- `data/panel.csv` — the full analysis dataset (200 firms x 5 years, 1,000 rows). Synthetic; generated with seed 20260912.
- `code/run.py` — reproduces Table 1 (descriptives) and Table 2 (OLS with year fixed effects).
- `paper/` — the tables as printed in the article, for comparison.
- `output/` — written by `run.py`.

## How to reproduce
```
python3 code/run.py
```
Runtime under one second. Requires Python 3.9 or later; no third-party packages.

## Output-to-article mapping
| Article | File |
|---|---|
| Table 1 | `output/table1.csv` |
| Table 2 | `output/table2.csv` |

## Data dictionary
firm (id), year, roa (return on assets, %), adopted (1 from adoption year on), size (log assets), age (years).

## Environment
Python 3.14.6, macOS 26 (Apple Silicon). Results are platform-independent (deterministic, no floating-point-order-sensitive operations beyond OLS on 1,000 rows).
