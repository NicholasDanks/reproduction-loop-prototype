#!/bin/bash
# 23-02078 x 3, Sonnet 5, Claude Code 2.1.280 (pinned, sha512 verified 20 Oct), isolated harness PLUS per-phase Stata
# ado isolation (profile.do + S_ADO; harness b9e3595-dirty, diff saved as HARNESS_DIFF_vs_b9e3595.patch in OUT).
# Same caps as the 15 Oct clean batch. Question: on a Stata with no leftover ados, does the agent find the three
# undeclared dependencies (grc1leg from its author site, ftools, require)? See replay_23-02078_2026-10-20/RESULT.md.
set -u
cd "$(dirname "$0")"
: "${CLAUDE_PIN_DIR:?}"
OUT="${COMPVAL_RUNS_ISO:-$HOME/compval_runs_iso}"
export PATH="$CLAUDE_PIN_DIR:$PATH" DISABLE_AUTOUPDATER=1
for v in $(env | cut -d= -f1 | grep -E '^(CLAUDECODE|CLAUDE_CODE_[A-Z_]+|CLAUDE_EFFORT|CLAUDE_PID|CLAUDE_JOB_DIR)$'); do unset "$v"; done
claude --version | grep -q '^2\.1\.280 ' || { echo "CLI is not 2.1.280: $(claude --version)"; exit 5; }
echo "=== START $(date)  out=$OUT  cli=$(claude --version)"
for rep in 1 2 3; do
  python3 loop/run_loop.py --backend claude --model claude-sonnet-5 --out "$OUT" --package "$HOME/compval_real/23-02078" --cap-apply 1800 --cap-run 900 --repeats 1 || { echo "ABORT rep $rep"; exit 1; }
done
echo "=== END $(date)"
