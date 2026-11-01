#!/usr/bin/env python3
"""Mutation testing of the verifier: plant known faults in packages the harness has already certified, run the
harness's own AFTER step (no model), and count which faults it catches ("kills").

A mutant is KILLED when the harness verdict is anything other than "reproduced" (rc == 0 and every ground-truth
value matched). A SURVIVOR is a fault the verifier certifies. Equivalent mutants (changes that cannot alter the
results) and benign mutants (reporting changes only) are included on purpose: an equivalent mutant should survive,
and a benign mutant that is killed is a false alarm.

  python3 tools/mutate.py --out DIR [--only fx01|23-02078]
Writes DIR/mutation_results.json and prints one line per mutant.
"""
import argparse, json, shutil, sys, tempfile, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "loop"))
import run_loop  # noqa: E402
from compare import compare  # noqa: E402

T1_START, T1_END = "*Table 1 (main text)", "*Table 1 ends here."
FORGED_T1 = "\r\n".join([
    'display "Table 1 top panel"', 'display "MainVar  0.189  -0.239  0.249  0.260  -0.045"',
    'display "        (0.102)  (0.102)  (0.115)  (0.102)  (0.121)"',
    'display "Table 1 bottom panel"', 'display "MainVar  0.182  -0.229  0.250  0.252  -0.103"',
    'display "        (0.113)  (0.110)  (0.115)  (0.110)  (0.129)"'])
FORGED_FX = '''    t1 = [("n_obs", 1000), ("n_firms", 200), ("mean_roa", 5.587821), ("share_adopted", 0.473)]
    t2 = [("const", 1.930177), ("adopted", 1.484756), ("size", 0.814856), ("age", -0.049514), ("year_2019", 0.089011),
          ("year_2020", -0.627041), ("year_2021", 0.335363), ("year_2022", 0.412863)]'''


def in_block(text, old, new, count=None):
    """Replace inside the Table 1 block only; assert the expected number of occurrences."""
    a = text.index(T1_START); b = text.index(T1_END, a)
    block = text[a:b]
    n = block.count(old)
    assert n and (count is None or n == count), f"{old!r} found {n} times in Table 1 block"
    return text[:a] + block.replace(old, new) + text[b:]


def once(text, old, new):
    assert text.count(old) == 1, f"{old!r} occurs {text.count(old)} times"
    return text.replace(old, new)


STATA_FILE = "data_analysis/do_files/02_analysis.do"
PY_FILE = "code/run.py"

# (id, class, file, function(text) -> text). Classes: design (analysis changed), data, forgery, labelling,
# equivalent (cannot change results), benign (reporting format only).
MUTANTS = {
    "23-02078": [
        ("S01_drop_controls_col1", "design", STATA_FILE, lambda t: in_block(t,
            "stchoicesum       performance_15 performance_25 performance_60 (MainVar", "stchoicesum       (MainVar", 1)),
        ("S02_se_robust_not_cluster", "design", STATA_FILE, lambda t: in_block(t, "cluster(participant) nocons", "vce(robust) nocons", 10)),
        ("S03_no_oriv_doubling", "design", STATA_FILE, lambda t: in_block(t, "expand 2, generate(replicant)", "gen replicant=0", 1)),
        ("S04_wrong_dv_col3", "design", STATA_FILE, lambda t: in_block(t,
            "eststo: ivregress 2sls stcompete_sum     performance_15 performance_25 performance_60 (MainVar",
            "eststo: ivregress 2sls stswitching_sum   performance_15 performance_25 performance_60 (MainVar", 1)),
        ("S05_drop_10_obs", "data", STATA_FILE, lambda t: in_block(t,
            "keep if game==1 //only 1 observation per participant", "keep if game==1 //only 1 observation per participant\r\ndrop in 1/10", 1)),
        ("S06_sign_flip_dv_col1", "design", STATA_FILE, lambda t: in_block(t, "egen stchoicesum=std(choicesum)", "egen stchoicesum=std(-choicesum)", 1)),
        ("S07_column_swap_top", "labelling", STATA_FILE, lambda t: in_block(t,
            "eststo: ivregress 2sls stchoicesum       performance_15 performance_25 performance_60 (MainVar=Instrument) constant*, cluster(participant) nocons\r\n"
            "eststo: ivregress 2sls stswitching_sum   performance_15 performance_25 performance_60 (MainVar=Instrument) constant*, cluster(participant) nocons",
            "eststo: ivregress 2sls stswitching_sum   performance_15 performance_25 performance_60 (MainVar=Instrument) constant*, cluster(participant) nocons\r\n"
            "eststo: ivregress 2sls stchoicesum       performance_15 performance_25 performance_60 (MainVar=Instrument) constant*, cluster(participant) nocons", 1)),
        ("S08_forged_table_printed", "forgery", STATA_FILE, lambda t: t[:t.index(T1_START)] + T1_START + "\r\n" + FORGED_T1 + "\r\n" + t[t.index(T1_END):]),
        ("S09_liml_not_2sls", "equivalent", STATA_FILE, lambda t: in_block(t, "ivregress 2sls", "ivregress liml", 10)),
        ("S10_print_b2_not_b3", "benign", STATA_FILE, lambda t: in_block(t, "se(3) b(3)", "se(3) b(2)", 2)),
    ],
    "fx01_resilient": [
        ("F01_drop_size", "design", PY_FILE, lambda t: once(once(t, 'r["adopted"], r["size"], r["age"]]', 'r["adopted"], r["age"]]'),
                                                         '["const", "adopted", "size", "age"]', '["const", "adopted", "age"]')),
        ("F02_sign_flip_y", "design", PY_FILE, lambda t: once(t, 'y = [r["roa"] for r in rows]', 'y = [-r["roa"] for r in rows]')),
        ("F03_drop_year_fe", "design", PY_FILE, lambda t: once(once(t, ' + [1.0 if r["year"] == yy else 0.0 for yy in years[1:]]', ''),
                                                            ' + [f"year_{yy}" for yy in years[1:]]', '')),
        ("F04_exclude_2022", "data", PY_FILE, lambda t: once(t, "    t1, t2 = analysis(rows)", "    rows = [r for r in rows if r['year'] != 2022]\n    t1, t2 = analysis(rows)")),
        ("F05_half_sample", "data", PY_FILE, lambda t: once(t, "    t1, t2 = analysis(rows)", "    rows = rows[:len(rows)//2]\n    t1, t2 = analysis(rows)")),
        ("F06_shuffled_y", "data", PY_FILE, lambda t: once(t, "    t1, t2 = analysis(rows)",
            "    import random; ys = [r['roa'] for r in rows]; random.Random(1).shuffle(ys)\n    for r, v in zip(rows, ys): r['roa'] = v\n    t1, t2 = analysis(rows)")),
        ("F07_label_swap", "labelling", PY_FILE, lambda t: once(t, '["const", "adopted", "size", "age"]', '["const", "size", "adopted", "age"]')),
        ("F08_pseudo_data", "data", "data/panel.csv", "COPY:fixtures/fx02_potemkin/data/panel.csv"),
        ("F09_forged_tables", "forgery", PY_FILE, lambda t: once(t, "    t1, t2 = analysis(rows)", FORGED_FX)),
        ("F10_reorder_regressors", "equivalent", PY_FILE, lambda t: once(once(t, 'r["adopted"], r["size"], r["age"]]', 'r["age"], r["size"], r["adopted"]]'),
                                                                 '["const", "adopted", "size", "age"]', '["const", "age", "size", "adopted"]')),
        ("F11_print_4dp", "benign", PY_FILE, lambda t: once(t, 'w.writerow(["term", "estimate"]); [w.writerow([k, f"{v:.6f}"])', 'w.writerow(["term", "estimate"]); [w.writerow([k, f"{v:.4f}"])')),
    ],
}
BASES = {
    "23-02078": dict(src=Path.home() / "compval_runs_iso/23-02078/claude/claude-sonnet-5/rep1/work",
                     paper=ROOT / "real/23-02078/paper", entry="data_analysis/do_files/00_master.do"),
    "fx01_resilient": dict(src=ROOT / "fixtures/fx01_resilient", paper=ROOT / "fixtures/fx01_resilient/paper", entry="code/run.py"),
}
SKIP = shutil.ignore_patterns("paper", "FIXTURE.md", ".venv*", "__pycache__", "*.log", "stata_batch_output.txt", "_compval_run.do", "profile.do")


def run_one(pkg_id, mid, mclass, target, op, out):
    base = BASES[pkg_id]; work = out / pkg_id / mid
    shutil.rmtree(work, ignore_errors=True); shutil.copytree(base["src"], work, ignore=SKIP)
    if (work / "output").exists():   # outputs must be regenerated, never inherited
        for p in (work / "output").glob("*"): p.unlink() if p.is_file() else None
    if op is not None:
        f = work / target
        if isinstance(op, str) and op.startswith("COPY:"):
            shutil.copy(ROOT / op[5:], f)
        else:
            raw = f.read_bytes().decode("utf-8", "replace")
            f.write_bytes(op(raw).encode("utf-8"))
    time.sleep(1)
    env = run_loop.stata_phase(work, out / pkg_id / f"{mid}_ado") if base["entry"].endswith(".do") else None
    r = run_loop.run_entry(work, base["entry"], 900, env=env)
    c = compare(work, base["paper"], outputs=r.get("outputs", []))
    shutil.rmtree(work / ".venv_run", ignore_errors=True)
    reproduced = (r.get("rc") == 0) and c["n_terms"] > 0 and c["n_match"] == c["n_terms"]
    res = dict(package=pkg_id, mutant=mid, mclass=mclass, rc=r.get("rc"), failure=r.get("failure"),
               n_match=c["n_match"], n_terms=c["n_terms"], verdict="reproduced" if reproduced else "not reproduced",
               killed=not reproduced)
    print(f"{pkg_id:15s} {mid:28s} {mclass:10s} rc={res['rc']} match={c['n_match']}/{c['n_terms']} -> "
          f"{'KILLED' if res['killed'] else 'survived'}", flush=True)
    return res


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", required=True); ap.add_argument("--only")
    a = ap.parse_args(); out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    results = []
    for pkg_id, muts in MUTANTS.items():
        if a.only and a.only not in pkg_id: continue
        results.append(run_one(pkg_id, "S00_control_unmutated" if pkg_id != "fx01_resilient" else "F00_control_unmutated", "control", None, None, out))
        for mid, mclass, target, op in muts:
            try:
                results.append(run_one(pkg_id, mid, mclass, target, op, out))
            except AssertionError as e:
                results.append(dict(package=pkg_id, mutant=mid, mclass=mclass, error=f"mutation did not apply: {e}"))
                print(f"{pkg_id:15s} {mid:28s} NOT APPLIED: {e}", flush=True)
    (out / "mutation_results.json").write_text(json.dumps(results, indent=1))


if __name__ == "__main__":
    main()
