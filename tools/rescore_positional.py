#!/usr/bin/env python3
"""Kernel-bug protocol: re-score recorded verdicts under the current comparator (positional rule, 2026-10-21) without
rerunning anything or calling a model, and report which verdicts flip.

  python3 tools/rescore_positional.py OUT.json RUN_OR_MUTANT_DIR ...
Each DIR is either a harness run (report.json + work/) or a mutant work dir from tools/mutate.py (scored against
real/23-02078/paper or fixtures/fx01_resilient/paper).
"""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "loop")); from compare import compare  # noqa: E402

def outputs_of(work):
    return sorted(str(p.relative_to(work)) for p in work.rglob("*") if p.is_file() and ".venv" not in str(p) and p.stat().st_size > 0)

rows = []
for d in map(Path, sys.argv[2:]):
    if (d / "report.json").exists():
        r = json.loads((d / "report.json").read_text()); work = d / "work"; pkg = r["package"]
        old = r["after"]["compare"]; rc = r["after"].get("rc"); label = f"run {pkg} {d.name}"
    else:
        work = d; pkg = d.parent.name; label = f"mutant {pkg} {d.name}"
        mr = {(x["package"], x["mutant"]): x for x in json.loads((d.parent.parent / "mutation_results.json").read_text())}[(pkg, d.name)]
        old = dict(n_match=mr["n_match"], n_terms=mr["n_terms"]); rc = mr["rc"]
    paper = ROOT / ("real/23-02078/paper" if pkg == "23-02078" else "fixtures/fx01_resilient/paper")
    new = compare(work, paper, outputs=outputs_of(work))
    ok = lambda c: rc == 0 and c["n_terms"] > 0 and c["n_match"] == c["n_terms"]
    row = dict(item=label, old=f"{old['n_match']}/{old['n_terms']}", new=f"{new['n_match']}/{new['n_terms']}",
               old_verdict="reproduced" if ok(old) else "not reproduced", new_verdict="reproduced" if ok(new) else "not reproduced",
               rules={k: v.get("rule") for k, v in (new.get("per_table") or {}).items() if isinstance(v, dict) and v.get("rule")})
    row["flipped"] = row["old_verdict"] != row["new_verdict"]; rows.append(row)
    print(f"{label:55s} {row['old']:>6s} -> {row['new']:>6s}  {row['old_verdict']:15s} -> {row['new_verdict']:15s} {'FLIP' if row['flipped'] else ''}")
Path(sys.argv[1]).write_text(json.dumps(rows, indent=1))
print(f"{sum(r['flipped'] for r in rows)} of {len(rows)} verdicts flipped")
