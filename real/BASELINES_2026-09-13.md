# As-shipped baselines (no agent), 13 Sep 2026

Protocol: fresh venv, install only what the package declares, run the staged entry, 15-min cap.
Stata 18 MP for the do-file. Ground truth per `real/<pkg>/paper/manifest.json`.

| package | entry | rc | first failure | note |
|---|---|---|---|---|
| 22-03335 | code.py | 1 | missing-dep (numpy) | no requirements file; Colab-origin script |
| 23-02958 | draw.py | 1 | missing-dep (simpy) | no requirements file |
| 22-00832 | simulation/sim_static.py | 1 | missing-dep (pyomo) | and IPOPT would be next |
| 23-02078 | data_analysis/do_files/00_master.do | r(601) | `ssc install grc1leg` not found at SSC | inline dependency install in the master; the command has moved off SSC. Stata's own API drift |
| 23-04183 | bash_all.sh | 127 | `python: command not found` | macOS has no `python` alias; the study's system-level-deviation case |
| 24-05365 | CstrAtrb-Final-Main-Only.ipynb | 1 | missing-dep (numpy) | no requirements file; kernel spec `myenv` |

0/6 run as shipped; 0 claims produced; 0 values matched. This is the floor the agent runs start from.
The May 2026 study reported non-zero strict scores for 22-03335 and 23-02958 because it ran against a
system Python that already had numpy; under a clean venv the first import fails. Protocol choice, not a
package property, and the manifest records it.
