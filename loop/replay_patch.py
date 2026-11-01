#!/usr/bin/env python3
"""Patch-replay tier: apply a recorded agent diff to a fresh copy of the shipped package and rerun it with the
harness's own AFTER step (fresh venv for Python; empty ado folders for Stata). No model is involved.

  python3 loop/replay_patch.py --run-dir ~/compval_runs_clean/23-02078/claude/claude-sonnet-5/rep1 [--out DIR]
  python3 loop/replay_patch.py --all ~/compval_runs_clean --real-only --out DIR     (every run; writes replay_all.json)

The paper used for scoring is the run's own paper_withheld/. Diffs recorded before 20 Oct 2026 were written in
text mode and lost the CR of CRLF files, so a hunk that fails exactly is retried with --ignore-whitespace;
the mode used is recorded.
"""
import argparse, json, re, shutil, subprocess, sys, tempfile, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from compare import compare  # noqa: E402
import run_loop  # noqa: E402


def apply_diff(pkg, diff_path):
    text = Path(diff_path).read_bytes().decode("utf-8", "replace")
    if not text.strip():
        return 0, "empty diff"
    m = re.search(r"^--- (\S+/orig)/", text, re.M)
    strip = m.group(1).count("/") + 1 if m else 1
    args = ["patch", f"-p{strip}", "--forward", "--batch", "-i", str(Path(diff_path).resolve())]
    mode = "exact"
    if subprocess.run(args + ["--dry-run"], cwd=pkg, capture_output=True).returncode != 0:
        args.append("--ignore-whitespace"); mode = "ignore-whitespace"
    p = subprocess.run(args, cwd=pkg, capture_output=True, text=True)
    return p.returncode, f"[{mode}] " + (p.stdout + p.stderr)[-800:]


def replay(run, out, cap):
    rep = json.loads((run / "report.json").read_text())
    pkg = out / "pkg"
    shutil.rmtree(out, ignore_errors=True); out.mkdir(parents=True)
    shutil.copytree(run / "orig", pkg)
    prc, plog = apply_diff(pkg, run / "changes.diff")
    entry = rep["after"].get("entry") or rep.get("entry")
    if not (pkg / entry).exists():
        entry = rep.get("entry")
    time.sleep(1)
    env = run_loop.stata_phase(pkg, out / "stata_after") if entry and entry.endswith(".do") else None
    r = run_loop.run_entry(pkg, entry, cap, env=env)
    cmp = compare(pkg, run / "paper_withheld", outputs=r.get("outputs", []))
    shutil.rmtree(pkg / ".venv_run", ignore_errors=True)
    ra = rep["after"]["compare"]
    res = dict(package=rep["package"], rep=rep["rep"], entry=entry, patch_rc=prc, patch_log=plog,
               rc=r.get("rc"), failure=r.get("failure"), error=r.get("error", "")[:200], seconds=r.get("seconds"),
               replay=dict(produced=cmp.get("claims_produced"), total=cmp.get("claims_total"), n_match=cmp.get("n_match"), n_terms=cmp.get("n_terms")),
               recorded_after=dict(rc=rep["after"].get("rc"), failure=rep["after"].get("failure"), produced=ra.get("claims_produced"),
                                   total=ra.get("claims_total"), n_match=ra.get("n_match"), n_terms=ra.get("n_terms")))
    res["same_as_recorded"] = (res["replay"]["produced"], res["replay"]["n_match"]) == (res["recorded_after"]["produced"], res["recorded_after"]["n_match"])
    (out / "replay.json").write_text(json.dumps(res, indent=1))
    print(f"{res['package']:12s} rep{res['rep']} patch={prc} rc={res['rc']} [{res['failure']}] "
          f"replay {res['replay']['produced']}/{res['replay']['total']} vals {res['replay']['n_match']}/{res['replay']['n_terms']} | "
          f"recorded {res['recorded_after']['produced']}/{res['recorded_after']['total']} vals {res['recorded_after']['n_match']}/{res['recorded_after']['n_terms']} "
          f"| {'SAME' if res['same_as_recorded'] else 'DIFFERS'}", flush=True)
    return res


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--run-dir"); g.add_argument("--all")
    ap.add_argument("--real-only", action="store_true"); ap.add_argument("--out"); ap.add_argument("--cap", type=int, default=900)
    a = ap.parse_args()
    out = Path(a.out).expanduser().resolve() if a.out else Path(tempfile.mkdtemp(prefix="replay_"))
    if a.run_dir:
        replay(Path(a.run_dir).expanduser().resolve(), out, a.cap)
        return
    runs = sorted(p.parent for p in Path(a.all).expanduser().glob("*/*/*/rep*/report.json"))
    if a.real_only:
        runs = [r for r in runs if not r.parts[-4].startswith("fx")]
    results = []
    for r in runs:
        try:
            results.append(replay(r, out / r.parts[-4] / r.name, a.cap))
        except Exception as e:  # one broken run must not stop the batch
            results.append(dict(package=r.parts[-4], rep=r.name, error=f"replay crashed: {e!r}"))
            print(f"{r.parts[-4]} {r.name} CRASHED {e!r}", flush=True)
    (out / "replay_all.json").write_text(json.dumps(results, indent=1))
    print(f"wrote {out / 'replay_all.json'}")


if __name__ == "__main__":
    main()
