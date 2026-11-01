#!/bin/zsh
# Rerun of the six real MNSC packages with the fixed harness (200 turns, broad allowlist).
# Run from a Terminal window, not from inside a Claude Code session.
# Pass 1: Claude Sonnet.  Pass 2: open-weight Qwen3 via Ollama.
cd ~/Documents/Projects/OrgSci_CFP/proposal3_COMPVAL/prototype
for p in 22-03335 23-02958 23-02078 23-04183 24-05365 22-00832; do
  python3 loop/run_loop.py --package ~/compval_real/$p --backend claude --model claude-sonnet-5 --cap-apply 1800 --cap-run 900
done
for p in 22-03335 23-02958 23-02078 23-04183 24-05365 22-00832; do
  python3 loop/run_loop.py --package ~/compval_real/$p --backend ollama --model qwen3:30b-a3b --cap-apply 1800 --cap-run 900
done
