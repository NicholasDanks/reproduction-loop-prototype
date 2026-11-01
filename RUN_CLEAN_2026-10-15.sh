#!/bin/bash
# Clean COMPVAL Claude batch (15 Oct 2026; Nick approved "fix + 28 clean runs").
# 10 fixture runs (fx02 x3, fx03 x3, fx04 x3, fx05 x1, as in the 12 Sep grid) + the six real MNSC packages x 3 repeats
# (test-retest), all Sonnet 5 (claude-sonnet-5), isolated harness (see AUDIT_agent_isolation_2026-10-15.md).
# Claude Code pinned to 2.1.280, the build used for AI_phd_student block A:
#   npm pack @anthropic-ai/claude-code-darwin-arm64@2.1.280   (sha512 ctkNgja8Yi2kngVFPO2667k6zbtJwjQ+dOTeEp1XmzHcoDFdaee4h4WVgZllsewm/Io+pPPPSFQVdGHOtdE/1A==)
#   and point CLAUDE_PIN_DIR at a folder holding its `claude` binary.
# Inherited Claude Code session variables are removed, matching the 17 Sep pass, which ran from a Terminal.
# Stops at the first run that fails the isolation or model check. Reps auto-increment, so a relaunch adds reps.
set -u
cd "$(dirname "$0")"
: "${CLAUDE_PIN_DIR:?set CLAUDE_PIN_DIR to the folder holding the 2.1.280 claude}"
OUT="${COMPVAL_RUNS_CLEAN:-$HOME/compval_runs_clean}"
export PATH="$CLAUDE_PIN_DIR:$PATH" DISABLE_AUTOUPDATER=1
for v in $(env | cut -d= -f1 | grep -E '^(CLAUDECODE|CLAUDE_CODE_[A-Z_]+|CLAUDE_EFFORT|CLAUDE_PID|CLAUDE_JOB_DIR)$'); do unset "$v"; done
claude --version | grep -q '^2\.1\.280 ' || { echo "CLI is not 2.1.280: $(claude --version)"; exit 5; }
echo "=== START $(date)  out=$OUT  harness=$(git rev-parse --short HEAD)  cli=$(claude --version)"
run() { python3 loop/run_loop.py --backend claude --model claude-sonnet-5 --out "$OUT" "$@" || { echo "ABORT: $*"; exit 1; }; }
for f in fx02_potemkin fx03_hidden_rng fx04_api_drift; do run --package "fixtures/$f" --repeats 3; done
run --package fixtures/fx05_stata_hardpath --repeats 1
for rep in 1 2 3; do
  for p in 22-03335 23-02958 23-02078 23-04183 24-05365 22-00832; do
    run --package "$HOME/compval_real/$p" --cap-apply 1800 --cap-run 900 --repeats 1
  done
done
echo "=== END $(date)"
