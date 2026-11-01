#!/usr/bin/env python3
"""Claims as consumer-written tests (prototype). Clauses are written from the ARTICLE (its Table 1 and notes), not from
the code, then checked against a package that the harness has already rerun.

Three kinds of clause:
  VALUE      positional: each reported number must appear in its own table cell (panel, column, coefficient or SE),
             not merely somewhere in the output (the presence rule in loop/compare.py).
  DESIGN     a stated method must be implemented in the code that ran (checked statically on the executed source;
             the rerun establishes that the source ran).
  DEPENDENCE outputs must change when the input data are perturbed (catches outputs not computed from the data).

The step that maps the article's words to variable names ("games solved under the 15-second limit" ->
performance_15) was done by hand for this prototype on 20 Oct 2026; in Stage 2 that is the auditor agent's job.

  python3 tools/claim_tests.py --mutants DIR     (DIR = output of tools/mutate.py; writes DIR/claim_results.json)
"""
import argparse, csv, json, random, re, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "loop"))
from compare import read_table  # noqa: E402

T1_START, T1_END = "Table 1 (main text)", "Table 1 ends here"
NUM = re.compile(r"[-−]?\d+\.\d+|[-−]?\d+")

# ---------------- 23-02078: written from the article's Table 1 and its notes ----------------
ARTICLE_T1 = {
    "top": {"b": [0.189, -0.239, 0.249, 0.260, -0.045], "se": [0.102, 0.102, 0.115, 0.102, 0.121]},
    "bottom": {"b": [0.182, -0.229, 0.250, 0.252, -0.103], "se": [0.113, 0.110, 0.115, 0.110, 0.129]},
    "N": 209,
}
# Hand mapping (article term -> code name), recorded as the auditor step:
DV_ORDER = ["stchoicesum", "stswitching_sum", "stcompete_sum", "std_comp", "stperformance_sum"]  # Binary, Switching, Competition, Component, Performance
PERF_CONTROLS = ["performance_15", "performance_25", "performance_60"]  # "games solved under the 15-, 25- and 60-second limits"
PERSONALITY = ["stdcompetitive", "stdrisk", "stdneuroticism", "stdextraversion", "stdopenness", "stdagreeableness", "stdconscientiousness"]


def _segment(text):
    a = text.find(T1_START); b = text.find(T1_END, a)
    return text[a:b] if a >= 0 and b > a else ""


def _code_lines(seg):
    out = []
    for ln in seg.replace("\r", "").splitlines():
        s = ln.split("//")[0].strip()
        if s and not s.startswith("*"):
            out.append(s)
    return out


def stata_clauses(pkg):
    res = {}
    log = (pkg / "stata_batch_output.txt").read_text(errors="replace") if (pkg / "stata_batch_output.txt").exists() else ""
    rows = [ln for ln in _segment(log).splitlines()]
    mv = [i for i, ln in enumerate(rows) if ln.startswith("MainVar")]
    for k, panel in enumerate(["top", "bottom"]):
        if len(mv) > k:
            b = [float(x.replace("−", "-")) for x in NUM.findall(rows[mv[k]].replace("MainVar", ""))]
            se = [float(x) for x in NUM.findall(rows[mv[k] + 1])] if mv[k] + 1 < len(rows) else []
            nrow = next((r for r in rows[mv[k]:mv[k] + 6] if r.startswith("N ")), "")
            n = [int(float(x)) for x in NUM.findall(nrow)]
        else:
            b = se = n = []
        res[f"VALUE {panel} coefficients, columns 1-5 in order"] = [round(x, 3) for x in b] == ARTICLE_T1[panel]["b"]
        res[f"VALUE {panel} standard errors, columns 1-5 in order"] = [round(x, 3) for x in se] == ARTICLE_T1[panel]["se"]
        res[f"DESIGN {panel} N = 209 participants in every column"] = bool(n) and all(x == ARTICLE_T1["N"] for x in n)
    src = (pkg / "data_analysis/do_files/02_analysis.do").read_text(errors="replace")
    code = _code_lines(_segment(src))
    regs = [ln for ln in code if re.search(r"\b(ivregress|regress|reg|ivreg2)\b", ln)]
    res["DESIGN estimates come from 10 estimation commands (5 per panel)"] = len(regs) == 10
    res["DESIGN ORIV: sample doubled, each survey measure instruments the other"] = (
        any(ln.startswith("expand 2") for ln in code) and len(regs) == 10 and all("(MainVar=Instrument)" in r for r in regs))
    top, bot = regs[:5], regs[5:10]
    res["DESIGN column order Binary, Switching, Competition, Component, Performance"] = (
        len(regs) == 10 and all(f" {dv} " in r + " " for dv, r in zip(DV_ORDER * 2, top + bot)))
    res["DESIGN performance controls in columns 1-4 only (both panels)"] = len(regs) == 10 and all(
        all(c in r for c in PERF_CONTROLS) == (i < 4) for i, r in enumerate(top)) and all(
        all(c in r for c in PERF_CONTROLS) == (i < 4) for i, r in enumerate(bot))
    res["DESIGN lower panel controls for Big Five, risk and competitiveness"] = len(bot) == 5 and all(all(c in r for c in PERSONALITY) for r in bot)
    res["DESIGN robust standard errors (article wording)"] = len(regs) == 10 and all(re.search(r"vce\(robust\)|,\s*robust\b|\brobust\b", r) for r in regs)
    return res


# ---------------- fx01: written from the fixture's article tables ----------------
def fx_clauses(pkg, paper):
    res = {}
    out = read_table(pkg / "output/table2.csv") or {}
    want = read_table(paper / "table2.csv")
    res["VALUE Table 2 coefficient for each named term"] = bool(out) and all(k in out and abs(out[k] - v) < 1e-5 for k, v in want.items())
    # DEPENDENCE: shuffle the outcome column and rerun; the coefficients must change.
    tmp = pkg.parent / (pkg.name + "_perturbed")
    shutil.rmtree(tmp, ignore_errors=True); shutil.copytree(pkg, tmp)
    f = tmp / "data/panel.csv"
    rows = list(csv.DictReader(open(f))); ys = [r["roa"] for r in rows]; random.Random(7).shuffle(ys)
    for r, y in zip(rows, ys): r["roa"] = y
    with open(f, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    (tmp / "output/table2.csv").unlink(missing_ok=True)
    subprocess.run([sys.executable, "code/run.py"], cwd=tmp, capture_output=True, timeout=300)
    pert = read_table(tmp / "output/table2.csv") or {}
    same = bool(pert) and all(k in pert and abs(pert[k] - v) < 1e-5 for k, v in want.items())
    res["DEPENDENCE coefficients change when the outcome is shuffled"] = bool(pert) and not same
    shutil.rmtree(tmp, ignore_errors=True)
    return res


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--mutants", required=True)
    d = Path(ap.parse_args().mutants)
    mres = {(r["package"], r["mutant"]): r for r in json.loads((d / "mutation_results.json").read_text())}
    out = []
    for (pkg, mid), r in sorted(mres.items()):
        work = d / pkg / mid
        if "error" in r or not work.exists(): continue
        clauses = stata_clauses(work) if pkg == "23-02078" else fx_clauses(work, ROOT / "fixtures/fx01_resilient/paper")
        failed = [k for k, v in clauses.items() if not v]
        out.append(dict(package=pkg, mutant=mid, mclass=r["mclass"], harness_killed=r["killed"], clauses=clauses,
                        failed=failed, claims_killed=bool(failed)))
        print(f"{pkg:15s} {mid:28s} harness={'KILLED' if r['killed'] else 'survived':8s} claims={'KILLED' if failed else 'pass':6s} {'; '.join(failed)[:150]}")
    (d / "claim_results.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
