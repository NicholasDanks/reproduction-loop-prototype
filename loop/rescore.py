"""Re-score existing run directories under the 17 Sep comparator rules without rerunning anything.

Rules applied post hoc: (1) zero-byte outputs do not count; (2) .log files the run created (present in
work/, absent from orig/, non-empty) are added to the output list so Stata batch logs are compared.
Original compare blocks are preserved under compare_v1. Usage: python3 loop/rescore.py [runs_root]
"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent)); import run_loop as rl

def _skip(p): return any(part.startswith(".venv") or "venv" in part.lower() or part in ("__pycache__", "site-packages", ".ipynb_checkpoints", "env", ".git") for part in p.parts)

root = Path(sys.argv[1] if len(sys.argv) > 1 else Path.home() / "compval_runs")
for rep in sorted(root.glob("*/*/*/rep*/report.json")):
    d = rep.parent; r = json.loads(rep.read_text()); work, orig, hold = d / "work", d / "orig", d / "paper_withheld"
    if not (work.exists() and hold.exists()): continue
    changed = False
    for phase in ("before", "after"):
        ph = r.get(phase) or {}
        outs = [o for o in ph.get("outputs", []) if (work / o).is_file() and (work / o).stat().st_size > 0]
        if phase == "after":
            outs += [str(p.relative_to(work)) for p in work.rglob("*.log")
                     if p.is_file() and p.stat().st_size > 0 and p.name != "_compval_run.log" and not (orig / p.relative_to(work)).exists()
                     and str(p.relative_to(work)) not in outs and not _skip(p)]
        outs = sorted(set(outs))
        new = rl.compare(work, hold, outputs=outs)
        old = ph.get("compare", {})
        if new != old:
            ph.setdefault("compare_v1", old); ph["compare"] = new; ph["outputs_v2"] = outs; changed = True
            print(f"{d.relative_to(root)} {phase}: {old.get('n_match')}/{old.get('n_terms')} c{old.get('claims_produced')}/{old.get('claims_total')} -> "
                  f"{new['n_match']}/{new['n_terms']} c{new['claims_produced']}/{new['claims_total']}")
    if changed: rep.write_text(json.dumps(r, indent=2))
