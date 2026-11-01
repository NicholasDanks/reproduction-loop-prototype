#!/bin/bash
# Six Organization Science packages x 1, Sonnet 5, Claude Code 2.1.280 (pinned), isolated harness (Stata per-phase ado
# isolation; R runs record host dependencies, not isolated). Nick approved "Sonnet 5, 1 rep" (21 Oct). Value manifests
# are built from the paper-only claims manifests (auditor_dryrun_2026-10-21), VALUE items, presence rule; positional
# and claim-test checking follow after the runs.
set -u
cd "$(dirname "$0")"
: "${CLAUDE_PIN_DIR:?}"
OUT="${COMPVAL_RUNS_ORSC:-$HOME/compval_runs_orsc}"
export PATH="$CLAUDE_PIN_DIR:$PATH" DISABLE_AUTOUPDATER=1
for v in $(env | cut -d= -f1 | grep -E '^(CLAUDECODE|CLAUDE_CODE_[A-Z_]+|CLAUDE_EFFORT|CLAUDE_PID|CLAUDE_JOB_DIR)$'); do unset "$v"; done
claude --version | grep -q '^2\.1\.280 ' || { echo "CLI is not 2.1.280: $(claude --version)"; exit 5; }
echo "=== START $(date)  out=$OUT  harness=$(git rev-parse --short HEAD)  cli=$(claude --version)"
for p in ORSC-2023.18288 ORSC-2021.1545 ORSC-2023.18332 ORSC-2022.1584 ORSC-2021.15751 ORSC-2023.17357; do
  echo "--- $p $(date)"
  python3 loop/run_loop.py --backend claude --model claude-sonnet-5 --out "$OUT" --package "$HOME/compval_real/$p" --cap-apply 1800 --cap-run 1800 --repeats 1 || echo "FAILED $p (continuing)"
done
echo "=== END $(date)"
