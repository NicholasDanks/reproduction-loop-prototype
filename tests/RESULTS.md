# Fixture results

Interpreter 3.14.6; pandas venv: yes; Stata: yes. Tolerance 1e-05.

| fixture | verdict | as shipped | after fix / perturbation | Tier A (static) | key items | planted property |
|---|---|---|---|---|---|---|
| fx01_resilient | PASS | rc=0 match=12/12 | n/a | 64.3 | A2.1=1.0 A3.2=0.5 A5.2=1.0 A6.1= | none (reference) |
| fx02_potemkin | PASS | rc=0 match=2/12 | n/a | 64.3 | A2.1=1.0 A3.2=0.5 A5.2=1.0 A6.1= | pseudo data; runs, matches nothing |
| fx03_hidden_rng | PASS | rc=0 match=12/12 | rc=0 match=4/12 | 56.7 | A2.1=0.5 A3.2=0.5 A5.2=1.0 A6.1=0.0 | hidden RNG stream dependency |
| fx04_api_drift | PASS | rc=1 match=0/12 | rc=0 match=12/12 | 64.3 | A2.1=1.0 A3.2=0.5 A5.2=1.0 A6.1= | unpinned pandas, removed APIs |
| fx05_stata_hardpath | PASS | rc=170 match=0/12 | rc=0 match=12/12 | 57.1 | A2.1=1.0 A3.2=0.5 A5.2=0.5 A6.1= | hardcoded author path (A5.2) |
