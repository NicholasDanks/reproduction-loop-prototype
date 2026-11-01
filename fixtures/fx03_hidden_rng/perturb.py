"""Demonstrates the hidden-RNG dependency: one extra draw at the perturbation point changes Table 2.
Not part of the shipped package; a harness tool. Usage: python3 perturb.py"""
import csv, subprocess, sys, tempfile, shutil
from pathlib import Path
ROOT = Path(__file__).resolve().parent
src = (ROOT / "code" / "run.py").read_text()
marker = "    # --- PERTURBATION POINT"
assert marker in src
perturbed = src.replace(marker, "    run_id = rng.random()  # e.g. a logging id added by a well-meaning editor\n" + marker)
with tempfile.TemporaryDirectory() as tmp:
    t = Path(tmp) / "pkg"; shutil.copytree(ROOT, t, ignore=shutil.ignore_patterns("output", "perturb.py"))
    (t / "code" / "run.py").write_text(perturbed)
    subprocess.run([sys.executable, str(t / "code" / "run.py")], check=True, capture_output=True)
    before = {r["term"]: float(r["estimate"]) for r in csv.DictReader(open(ROOT / "paper" / "table2.csv"))}
    after = {r["term"]: float(r["estimate"]) for r in csv.DictReader(open(t / "output" / "table2.csv"))}
print(f"{'term':10s} {'paper':>10s} {'perturbed':>10s} {'delta':>10s}")
for k in before: print(f"{k:10s} {before[k]:10.4f} {after[k]:10.4f} {after[k]-before[k]:10.4f}")
