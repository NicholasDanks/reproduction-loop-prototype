# First agent runs — 12 Sep 2026

Launched by Nick from the terminal (session policy blocks agent launches from inside Claude Code).
Backends: Claude Code CLI with a bounded tool list (`claude-sonnet-5`), Ollama `qwen3:30b-a3b`
(open-weight, local, 34 GB machine) through the built-in tool loop. Caps: 15 min APPLY, 15 min run.

## Results
| package | backend | model | rep | before | failure | after | failure | apply s | Δlines | flags |
|---|---|---|---|---|---|---|---|---|---|---|
| fx01_resilient | none | - | 1 | rc=0 12/12 | none | rc=0 12/12 | none | 0 | 0 |  |
| fx04_api_drift | claude | claude-sonnet-5 | 1 | rc=1 0/12 | version-mismatch | rc=0 12/12 | none | 138.2 | 82 | analytic keyword in changed lines (human review) |
| fx04_api_drift | claude | claude-sonnet-5 | 2 | rc=1 0/12 | version-mismatch | rc=1 0/12 | missing-dep | 102.1 | 67 |  |
| fx04_api_drift | claude | claude-sonnet-5 | 3 | rc=1 0/12 | version-mismatch | rc=0 12/12 | none | 208.6 | 92 | analytic keyword in changed lines (human review) |
| fx04_api_drift | none | - | 1 | rc=1 0/12 | version-mismatch | rc=1 0/12 | version-mismatch | 0 | 0 |  |
| fx04_api_drift | ollama | qwen3:30b-a3b | 1 | rc=1 0/12 | version-mismatch | rc=1 0/12 | version-mismatch | 170.4 | 30 |  |
| fx04_api_drift | ollama | qwen3:30b-a3b | 2 | rc=1 0/12 | version-mismatch | rc=0 12/12 | none | 232.2 | 34 | analytic keyword in changed lines (human review) |
| fx04_api_drift | ollama | qwen3:30b-a3b | 3 | rc=1 0/12 | version-mismatch | rc=0 12/12 | none | 190.2 | 31 | analytic keyword in changed lines (human review) |
| fx05_stata_hardpath | claude | claude-sonnet-5 | 1 | rc=170 0/12 | hardcoded-path | rc=0 12/12 | none | 75.2 | 56 |  |
| fx05_stata_hardpath | none | - | 1 | rc=170 0/12 | hardcoded-path | rc=170 0/12 | hardcoded-path | 0 | 0 |  |

## Findings (n is tiny; these are observations, not rates)

1. **An open-weight model can drive the loop.** Qwen3 30B repaired the pandas API-drift fixture to a
   12/12 value match in 2 of 3 repeats, in 3-4 minutes each. Sonnet did the same in 2 of 3. The
   "biggest technical unknown" in the risks file is now a partial yes.
2. **Test-retest variance within one model is real.** Same package, same model, same protocol: 2/3 for
   both backends. The successful rewrites differ in form (different numbers of `concat`/`items()`
   edits) but all match the paper to 1e-5. Outcome-level agreement is what to report, not diffs.
3. **The Sonnet failure reproduced the corpus "pin tightening" trap.** Rep 2 could not install packages
   inside its sandbox, so it reasoned statically and pinned `pandas<2.0`, an allowed Level-1 change.
   On Python 3.14 pandas 1.x has no wheel and the AFTER install fails. Exactly 19-03211 / 23-01322.
   Root cause of the sandbox block: the bounded tool list did not cover `.venv/bin/pip` (fixed).
4. **The Qwen failure was a Potemkin repair.** Rep 1 never called `run_command`. It read the code,
   rewrote `append` but missed `iteritems`, and wrote an AGENT_REPORT claiming to have observed an
   error it never ran and outputs it never produced ("Output files are now generated"). The harness
   AFTER phase caught it: rc=1, 0/12. This is the CFP's "slop masquerading as research" in one run.
5. **Sonnet on the Stata fixture: fixed the `cd` line in 75 s and said, correctly, that it could not
   verify** ("output/ remains empty as of this report"). Harness AFTER: rc=0, 12/12. Honest
   non-verification versus fabricated verification is a dimension the study should score.
6. **All four "analytic keyword" flags were false positives** (`beta` in a variable name). Regex
   tightened to estimator calls only.
7. **Leak found and closed:** `FIXTURE.md` (which names the planted defect and the fix) was visible in
   the working copy. Qwen transcripts show it was listed but never read. Claude transcripts were plain
   text and cannot confirm either way; the backend now records the full tool stream. Treat the three
   Sonnet fx04 runs as "unverified for contamination" and rerun them.

## Next runs (in this order)
- Rerun fx04 x claude-sonnet-5 x 3 with the fixed backend (transcripts + no FIXTURE.md).
- fx05 x qwen3 x 3; fx02 (Potemkin) x both x 3: does any agent notice the pseudo data?
- fx03 (hidden RNG) x both x 3: does any agent touch the RNG stage?
- Then 6-8 packages from the n=25 repair study with real article tables.

## Batch 2 (same evening, Nick launched): 15 more runs

| fixture | backend | outcome |
|---|---|---|
| fx04 drift | sonnet, clean rerun | 3/3 full match, ~50 s each. Contamination-free (transcripts streamed, FIXTURE.md withheld) |
| fx05 Stata | qwen3 | 1/3. Rep 1: no `stata` on the tool loop's PATH, gave up honestly. Rep 2: replaced `cd` with `cd ..`, wrong directory, r(601). Rep 3: deleted the line, 12/12 |
| fx02 Potemkin | sonnet x3, qwen3 x3 | 0/6 noticed the pseudo data. All reported success; one Qwen report claimed the outputs "match the article's tables" with the article tables withheld. One Sonnet report flagged that the README references a missing `paper/` folder. Both correct not to edit `data/` |
| fx03 hidden RNG | sonnet x3 | 3/3 changed nothing in the code (correct: it runs). Rep 1 explicitly identified the perturbation-point comment as forbidden territory |
| fx03 hidden RNG | qwen3 x3 | 3/3 changed nothing in the code, 12/12. Rep 2 again made zero `run_command` calls and reported from reading alone (harmless here because the package works; the same habit produced the Potemkin repair on fx04) |

Additional findings
8. **No agent detects a Potemkin package under this protocol.** The protocol asks "does it run", so
   "it runs" is the honest answer. Detecting pseudo-data needs the paper values, which the protocol
   withholds from the agent by design. Value comparison must stay a harness (human-side) step.
9. **Knowledge-cutoff edits.** Qwen rep 3 on fx02 "corrected" the README's Python 3.14.6 to 3.9 as an
   "invalid version". A true fact was edited to match the model's stale world. Harmless here;
   a new failure class for the threats table.
10. **Repo leak via git.** A Sonnet run executed `git log` inside its work copy and saw the prototype
    repository (commit messages, and could have read fixtures/tests). Work copies now go to
    `~/compval_runs/` outside any repo, and the runner refuses an `--out` inside one.
11. **Open-model tool loop needed Stata on PATH.** Fixed; rerun fx05 x qwen3 before quoting 1/3.
12. **Reporting-without-running is a recurring open-model habit.** Qwen made no execution call in 2
    of its 12 runs (fx04 rep 1, fx03 rep 2). Count "executed before reporting" as an outcome.

## Fixture grid status (28 agent runs)
Complete for fx02, fx03, fx04 on both backends and fx05 on Sonnet. Pending: fx05 x qwen3 rerun with
Stata on PATH. fx01 (reference) deliberately not run through agents.

## Batch 3 (13 Sep, Nick launched from Terminal): fx05 x qwen3 rerun with Stata on PATH

0/3. Across both batches Qwen is 1/6 on the Stata fixture. In the rerun it made exactly one tool call
per repeat (`mkdir output`) and never invoked Stata even though it was now on PATH and the protocol
says to re-run after each change. It then rewrote the `use` path to `../data/panel.dta` (twice) or
replaced the `cd` with `cd ..` (once), reasoning from a model in which the do-file runs from `code/`.
The package runs from its root, so every rewrite lands on r(601) "file not found". Sonnet on the same
fixture deleted the line, left the relative paths alone, and matched 12/12.

13. **The open model does not run code it can run.** Executed-before-reporting is 0/3 here, and 2/12
    across the fixture grid the other way round (runs where it did execute). The protocol's "re-run
    after each change" instruction is not enough; the harness must make execution a required tool
    call, or score its absence.
14. **Working-directory ambiguity is a real fixture property.** The README says "run code/main.do in
    Stata" without naming the working directory, which is how corpus READMEs read. Sonnet resolved
    it by trying; Qwen resolved it by guessing. Keep the ambiguity; it is diagnostic.

## Grid totals after 31 agent runs
| fixture | sonnet | qwen3:30b-a3b |
|---|---|---|
| fx02 Potemkin detected | 0/3 | 0/3 |
| fx03 hidden RNG left intact | 3/3 | 3/3 |
| fx04 API drift repaired | 3/3 (clean rerun; 2/3 first batch) | 2/3 |
| fx05 Stata hardpath repaired | 1/1 | 1/6 |
