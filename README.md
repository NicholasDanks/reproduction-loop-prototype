# COMPVAL prototype: an AI reproduction loop under a locked human protocol

Prototype repository for the Organization Science "Call for Science" Stage-1 submission
(proposal 3; authors anonymized for review). Status: fixtures, harness and agent loop.

## Layout
- `fixtures/` — five synthetic replication packages we own outright, each with one planted property
  (see each `FIXTURE.md`): resilient reference, Potemkin pseudo-data, hidden RNG dependency, pandas
  API drift, Stata hardcoded path. Each ships `paper/` tables as the ground truth an article would print.
- `tests/run_fixtures.py` — runs every fixture as shipped, applies its documented fix or perturbation,
  compares outputs to the paper tables by term, and reports the deterministic Tier A score beside the
  execution result. `tests/RESULTS.md` is its output.
- `tools/` — the deterministic data generator and the OLS snippet the Python fixtures embed.
- `core/` — the deterministic Tier A scorer and the Stata batch runner that the harness and the loop import.

## Requirements
Python 3.12+ (stdlib) for fx01-03 and the harness; a venv with current pandas for fx04
(`python3 -m venv .venv_fx04 && .venv_fx04/bin/pip install pandas numpy`); Stata 17+ for fx05.
The deterministic scorer (`core/batch_assess_new.py`) and the Stata runner (`core/stata_runner.py`) ship in
`core/`; set `$COMPVAL_DIR` only to use another copy.

## The loop (`loop/`)
`loop/run_loop.py` runs the pre-registered protocol: deterministic BEFORE (fresh venv or Stata batch, run
entry, classify first failure), APPLY (an agent backend receives `loop/protocol.md` inside a temp copy with
the paper tables withheld), deterministic AFTER (rerun, compare to paper by term, diff, forbidden-change
flags). Backends in `loop/backends.json`: `none`, `claude` (bounded tool list), `gemini`, `ollama` /
any OpenAI-compatible endpoint (built-in minimal tool loop; refuses writes under `data/`).

```
python3 loop/run_loop.py --package fixtures/fx04_api_drift --backend claude --model claude-sonnet-5 --repeats 3
python3 loop/run_loop.py --package fixtures/fx05_stata_hardpath --backend ollama --model qwen3:30b-a3b
python3 loop/summarize.py
```
Runs land in `~/compval_runs/<package>/<backend>/<model>/rep<k>/` (outside the repo, deliberately: an agent inside the repo could read the fixtures and tests via git) with `report.json`, `changes.diff`, `agent_stdout.txt`.
