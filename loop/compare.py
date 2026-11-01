"""Compare a package's produced outputs to the article's ground truth. Stdlib only.

Two ground-truth formats, both under paper/ (withheld from the agent):
  1. Fixture format: paper/*.csv, matched by first-column name to output/<same name>.csv.
  2. Manifest format: paper/manifest.json listing claims
       {"id","kind":"table|figure|stat","files":[globs],"values":[{"label","value","digits"}]}
     A claim is PRODUCED if any produced/modified file matches a glob. Its VALUES are matched by
     scanning all produced text-like files (csv/txt/log/tex/md/json/html) for a numeric token that
     rounds to the value at the stated digits. Value matching is presence-based and can false-positive
     on short numbers; keep values at >= 3 significant digits.
     POSITIONAL (preferred, added 2026-10-21): a claim with "locate" is matched by position instead:
       "locate": {"file": glob, "start": text, "end": text, "row": label, "occurrence": k}
     selects the k-th line (1-based) starting with `row` inside the start..end segment of the first output
     matching `file`; each value then names "col" (1-based number on that line) and "offset" (0 = that
     line, 1 = the next line, e.g. standard errors under coefficients). The mutation pilot (2026-10-20)
     showed presence matching certifies altered tables because article values recur elsewhere in long logs.
     Every result records the rule used per claim ("rule": positional|presence).
"""
import csv, fnmatch, json, re
from pathlib import Path
TOL = 1e-5
TEXT_EXT = {".csv", ".txt", ".log", ".tex", ".md", ".json", ".html", ".tsv", ".out", ".smcl", ".rtf"}
NUM = re.compile(r"(?<![\w.])[-−–]?\d+(?:\.\d+)?(?![\w.])")
# LaTeX minus as R's stargazer and Stata's esttab write it ("$-$0.074"); without this every negative cell in a .tex
# table or console dump was missed (ORSC-2022.1584, 21 Oct 2026).
TEX_MINUS = re.compile(r"\$-\$|\$\{-\}\$|\\\(-\\\)|\$\\text\{-\}\$|\$\\textminus\$")
def _detex(text): return TEX_MINUS.sub("-", text)

def read_table(p):
    p = Path(p)
    if not p.exists(): return None
    rows = list(csv.reader(open(p, errors="replace"))); out = {}
    for r in rows[1:]:
        if len(r) >= 2:
            try: out[r[0].strip()] = float(r[1])
            except ValueError: pass
    return out

def _fixture_compare(pkg, paper_dir, tol):
    nm = nt = 0; per = {}
    for t in sorted(paper_dir.glob("*.csv")):
        paper = read_table(t); out = read_table(pkg / "output" / t.name)
        m = sum(1 for k, v in paper.items() if out and k in out and abs(out[k] - v) < tol)
        per[t.name] = (m, len(paper)); nm += m; nt += len(paper)
    return dict(mode="fixture", n_match=nm, n_terms=nt, per_table=per, claims_produced=None, claims_total=None)

def _numbers_in(path, limit=5_000_000):
    try: text = _detex(Path(path).read_text(errors="replace")[:limit])
    except Exception: return set()
    vals = set()
    for tok in NUM.findall(text):
        tok = tok.replace("−", "-").replace("–", "-")
        try: vals.add(float(tok))
        except ValueError: pass
    return vals

def _positional(pkg, claim, outputs):
    """Match each value at its stated cell; returns (n_matched, n_values)."""
    loc, vals = claim["locate"], claim["values"]
    src = next((o for o in outputs if fnmatch.fnmatch(o, loc["file"]) or fnmatch.fnmatch(Path(o).name, loc["file"])), None)
    if src is None: return 0, len(vals)
    try: text = _detex((Path(pkg) / src).read_text(errors="replace"))
    except Exception: return 0, len(vals)
    a = text.find(loc["start"]) if loc.get("start") else 0
    b = text.find(loc["end"], a) if loc.get("end") and a >= 0 else len(text)
    if a < 0 or b < 0: return 0, len(vals)
    lines = text[a:b].replace("\r", "").splitlines()
    rows = [i for i, ln in enumerate(lines) if ln.strip().startswith(loc["row"])]
    k = loc.get("occurrence", 1) - 1
    if len(rows) <= k: return 0, len(vals)
    vm = 0
    for v in vals:
        i = rows[k] + v.get("offset", 0)
        if i >= len(lines): continue
        line = lines[i].strip()
        if v.get("offset", 0) == 0: line = line[len(loc["row"]):]
        nums = [float(x.replace("−", "-").replace("–", "-")) for x in NUM.findall(line.replace("(", " ").replace(")", " ").replace("*", " "))]
        col = v["col"] - 1; d = v.get("digits", 3)
        vm += col < len(nums) and round(nums[col], d) == round(float(v["value"]), d)
    return vm, len(vals)

def _manifest_compare(pkg, manifest, outputs):
    outputs = [str(o) for o in outputs]
    produced = 0; per = {}; nm = nt = 0; numcache = {}
    for c in manifest["claims"]:
        files = [o for o in outputs if any(fnmatch.fnmatch(o, g) or fnmatch.fnmatch(Path(o).name, g) for g in c.get("files", []))]
        got = bool(files); produced += got
        vm = vt = 0
        if c.get("locate") and c.get("values"):
            vm, vt = _positional(pkg, c, outputs)
            nm += vm; nt += vt; got = vm > 0; produced += got - (1 if files else 0)
            per[c["id"]] = dict(produced=got, files=files[:5], values=(vm, vt), rule="positional"); continue
        for v in c.get("values", []):
            vt += 1; d = v.get("digits", 3); target = round(float(v["value"]), d)
            hit = False
            for o in outputs:
                if Path(o).suffix.lower() not in TEXT_EXT: continue
                if o not in numcache: numcache[o] = _numbers_in(pkg / o)
                if any(round(x, d) == target for x in numcache[o]): hit = True; break
            vm += hit
        if vt: got = vm > 0; produced += got - (1 if files else 0)   # a value-bearing claim is produced only if a value is found
        nm += vm; nt += vt; per[c["id"]] = dict(produced=got, files=files[:5], values=(vm, vt), rule="presence" if vt else None)
    return dict(mode="manifest", n_match=nm, n_terms=nt, per_table=per, claims_produced=produced, claims_total=len(manifest["claims"]))

def compare(pkg, paper_dir=None, tol=TOL, outputs=None):
    pkg = Path(pkg); paper_dir = Path(paper_dir) if paper_dir else pkg / "paper"
    mf = paper_dir / "manifest.json"
    if mf.exists(): return _manifest_compare(pkg, json.load(open(mf)), outputs or [])
    return _fixture_compare(pkg, paper_dir, tol)
