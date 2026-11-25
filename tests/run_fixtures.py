#!/usr/bin/env python3
"""Fixture harness: runs each synthetic replication package as shipped, applies its documented
Level-1/2 fix (or perturbation), reruns, compares output tables to the paper tables by term name,
and scores each package with the deterministic Tier A scorer. Stdlib only.

    python3 tests/run_fixtures.py            # writes tests/RESULTS.md, exit 1 on any expectation miss
Env: COMPVAL_DIR (default: core/ in this repository) for the scorer and the Stata runner.
"""
import csv, json, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FX = ROOT / "fixtures"
COMPVAL = Path(os.environ.get("COMPVAL_DIR", ROOT / "core"))
STATA = Path("/Applications/Stata/StataMP.app/Contents/MacOS/stata-mp")
VENV_PY = ROOT / ".venv_fx04" / "bin" / "python"
TOL = 1e-5

sys.path.insert(0, str(ROOT / "loop"))
from compare import compare as _compare
def compare(pkg):
    r = _compare(pkg); return r["n_match"], r["n_terms"]

def run_python(pkg, interp):
    p = subprocess.run([str(interp), str(pkg / "code" / "run.py")], cwd=pkg, capture_output=True, text=True, timeout=300)
    return p.returncode, (p.stderr.strip().splitlines() or [""])[-1][:120]

def run_stata(pkg):
    sys.path.insert(0, str(COMPVAL)); from stata_runner import run_do
    r = run_do(pkg / "code" / "main.do", cwd=pkg, timeout=300)
    return r["rc"], (r["errors"][0]["command"][:120] if r["errors"] else "")

FIX = {
    "fx04_api_drift": lambda pkg: (pkg / "code" / "run.py").write_text(
        re.sub(r"t1 = t1\.append\(\{(.*?)\}, ignore_index=True\)", r"t1 = pd.concat([t1, pd.DataFrame([{\1}])], ignore_index=True)",
               (pkg / "code" / "run.py").read_text()).replace("X.iteritems()", "X.items()")),
    "fx05_stata_hardpath": lambda pkg: (pkg / "code" / "main.do").write_text(
        "\n".join(l for l in (pkg / "code" / "main.do").read_text().splitlines() if not l.startswith('cd "C:')) + "\n"),
    "fx03_hidden_rng": lambda pkg: (pkg / "code" / "run.py").write_text(
        (pkg / "code" / "run.py").read_text().replace("    # --- PERTURBATION POINT", "    run_id = rng.random()\n    # --- PERTURBATION POINT")),
}

def static_score(pkg):
    sys.path.insert(0, str(COMPVAL))
    try:
        import batch_assess_new as b
        files = b.find_files(str(pkg)); scores, lang = b.score_package(str(pkg), files)
        return b.compute_tier_a(scores), scores
    except Exception as e:
        return None, {"error": str(e)[:80]}

def main():
    expected = json.load(open(ROOT / "tests" / "expected.json"))
    results = []; fail = 0
    for name, exp in expected.items():
        src = FX / name; kind = exp["kind"]
        if kind == "python-venv" and not VENV_PY.exists(): results.append((name, "SKIP", "no .venv_fx04", "", "", "", "")); continue
        if kind == "stata" and not STATA.exists(): results.append((name, "SKIP", "no Stata", "", "", "", "")); continue
        interp = VENV_PY if kind == "python-venv" else sys.executable
        tier_a, scores = static_score(src)
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp) / name; shutil.copytree(src, pkg, ignore=shutil.ignore_patterns("output", "perturb.py"))
            (pkg / "output").mkdir()
            rc, err = run_stata(pkg) if kind == "stata" else run_python(pkg, interp)
            nm, nt = compare(pkg); shipped = dict(rc=rc, match=f"{nm}/{nt}", err=err)
            after = None
            if name in FIX:
                shutil.rmtree(pkg / "output"); (pkg / "output").mkdir(); FIX[name](pkg)
                rc2, err2 = run_stata(pkg) if kind == "stata" else run_python(pkg, interp)
                nm2, nt2 = compare(pkg); after = dict(rc=rc2, match=f"{nm2}/{nt2}", err=err2)
        ok = True
        e = exp["shipped"]; ok &= (rc == 0) == e["runs"] and ((nm == nt and nt > 0) == e["matches"])
        if after and "after" in exp:
            e2 = exp["after"]; ok &= (after["rc"] == 0) == e2["runs"] and ((nm2 == nt2 and nt2 > 0) == e2["matches"])
        if not ok: fail += 1
        results.append((name, "PASS" if ok else "FAIL", f"rc={rc} match={shipped['match']}", f"rc={after['rc']} match={after['match']}" if after else "n/a",
                        tier_a, f"A2.1={scores.get('A2.1','?')} A3.2={scores.get('A3.2','?')} A5.2={scores.get('A5.2','?')} A6.1={scores.get('A6.1','?')}", exp["label"]))
    lines = ["# Fixture results", "", f"Interpreter {sys.version.split()[0]}; pandas venv: {'yes' if VENV_PY.exists() else 'no'}; Stata: {'yes' if STATA.exists() else 'no'}. Tolerance {TOL}.", "",
             "| fixture | verdict | as shipped | after fix / perturbation | Tier A (static) | key items | planted property |", "|---|---|---|---|---|---|---|"]
    for r in results: lines.append("| " + " | ".join(str(x) for x in r) + " |")
    (ROOT / "tests" / "RESULTS.md").write_text("\n".join(lines) + "\n"); print("\n".join(lines))
    sys.exit(1 if fail else 0)

if __name__ == "__main__":
    main()
