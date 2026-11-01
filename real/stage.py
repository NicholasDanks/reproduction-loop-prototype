#!/usr/bin/env python3
"""Stage a real MNSC package for the loop: copy it from the COMPVAL corpus into ~/compval_real/<pkg>/
and overlay real/<pkg>/paper/ (manifest) + ENTRY. Usage: python3 real/stage.py 23-02078 [...]"""
import json, os, shutil, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent; COMPVAL = Path(os.environ.get("COMPVAL_DIR", Path.home() / "Documents/Projects/COMPVAL"))
DEST = Path(os.environ.get("COMPVAL_REAL", Path.home() / "compval_real"))
for pkg in sys.argv[1:]:
    meta = json.load(open(ROOT / pkg / "stage.json")); src = COMPVAL / meta["source"]; dst = DEST / pkg
    if dst.exists(): shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__MACOSX", ".DS_Store", "COMPVAL_REPORT*", "*.log"))
    shutil.copytree(ROOT / pkg / "paper", dst / "paper", dirs_exist_ok=True)
    (dst / ".compval_entry").write_text(meta["entry"] + "\n")
    print(f"staged {pkg} -> {dst}  entry={meta['entry']}  ({sum(f.stat().st_size for f in dst.rglob('*') if f.is_file())/1e6:.0f} MB)")
