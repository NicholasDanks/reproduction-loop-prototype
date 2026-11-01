#!/usr/bin/env python3
"""Aggregate runs/**/report.json into a package x backend x model table (markdown to stdout)."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
rows = []
import os
RUNS = Path(os.environ.get("COMPVAL_RUNS", Path.home() / "compval_runs"))
for rp in sorted(list(RUNS.rglob("report.json")) + list((ROOT / "runs").rglob("report.json"))):
    r = json.load(open(rp)); b, a = r["before"], r["after"]
    def fmt(c): return f"{c['n_match']}/{c['n_terms']}" + (f" c{c['claims_produced']}/{c['claims_total']}" if c.get('claims_total') is not None else "")
    rows.append((r["package"], r["backend"], r["model"] or "-", r["rep"], f"rc={b['rc']} {fmt(b['compare'])}", b["failure"],
                 f"rc={a['rc']} {fmt(a['compare'])}", a["failure"], r["apply"]["seconds"], r["apply"].get("changed_lines", 0), f"{r['apply'].get('exec_calls','?')}/{r['apply'].get('tool_calls','?')}", r["apply"].get("denied_calls", "?"), "; ".join(r["apply"].get("flags", []))))
print("| package | backend | model | rep | before | failure | after | failure | apply s | Δlines | exec/tools | denied | flags |"); print("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
for r in rows: print("| " + " | ".join(str(x) for x in r) + " |")
