#!/usr/bin/env python3
"""Training-data contamination probe: can a model recite an article's ground-truth values from memory?

Each model gets the article's title, journal and year (the strongest cue a contaminated model could use), no
tools, no package, no paper, and is asked for the values reported in the manifest's table. Responses are scored
with the harness's own presence rule (a manifest value counts if any number in the response rounds to it).
Control: every response is also scored against every OTHER package's manifest, which estimates chance matching
for a response that emits that many numbers. Contamination shows up as own-package matches clearly above
the cross-package rate.

  python3 tools/contamination_probe.py --out DIR [--models claude-sonnet-5 claude-opus-5-5]
"""
import argparse, json, os, re, subprocess, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NUM = re.compile(r"[-−–]?\d*\.\d+|[-−–]?\d+")

ARTICLES = {
    "23-02078": ("Time Pressure Preferences", "Table 1 (both panels: the coefficient on time-pressure preference in columns 1-5, with standard errors)"),
    "22-00832": ("Dynamic Pricing for Two-Sided Marketplaces with Offer Expiration", "the main numerical results table"),
    "23-04183": ("Care for the Mind amid Chronic Diseases: An Interpretable AI Approach Using IoT", "the main results table (model performance)"),
    "24-05365": ("Performance Attribution for Portfolio Constraints", "Table 1"),
}
PROMPT = ("From memory only (you have no tools and no documents): the article \"{title}\" was published in "
          "Management Science (2024-2025). List every number you can recall from {what}. If you do not "
          "remember the values, say so plainly instead of estimating.")


def manifest_values(pkg):
    m = json.loads((ROOT / "real" / pkg / "paper" / "manifest.json").read_text())
    return [(round(float(v["value"]), v.get("digits", 3)), v.get("digits", 3)) for c in m["claims"] for v in c.get("values", [])]


def score(text, values):
    nums = set()
    for tok in NUM.findall(text):
        try: nums.add(float(tok.replace("−", "-").replace("–", "-")))
        except ValueError: pass
    return sum(any(round(x, d) == t for x in nums) for t, d in values), len(values), len(nums)


def ask(model, prompt):
    env = {k: v for k, v in os.environ.items() if not k.startswith(("CLAUDECODE", "CLAUDE_CODE_"))}
    with tempfile.TemporaryDirectory() as d:   # empty cwd: no CLAUDE.md, no project files
        p = subprocess.run(["claude", "-p", "--model", model, "--setting-sources", "local", "--strict-mcp-config",
                            "--disable-slash-commands", "--tools", ""],
                           input=prompt, cwd=d, capture_output=True, text=True, timeout=300, env=env)
    out = p.stdout.strip()
    if p.returncode != 0 or not out or out.startswith("Error:"):
        raise RuntimeError(f"claude call failed ({p.returncode}): {(out or p.stderr)[:300]}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True); ap.add_argument("--models", nargs="+", default=["claude-sonnet-5", "claude-opus-5-5"])
    a = ap.parse_args(); out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    vals = {p: manifest_values(p) for p in ARTICLES}
    rows = []
    for model in a.models:
        for pkg, (title, what) in ARTICLES.items():
            text = ask(model, PROMPT.format(title=title, what=what))
            (out / f"{model}_{pkg}.txt").write_text(text)
            own = score(text, vals[pkg])
            cross = [score(text, vals[q])[:2] for q in ARTICLES if q != pkg]
            rows.append(dict(model=model, package=pkg, own_match=own[0], own_terms=own[1], numbers_emitted=own[2],
                             cross_match=sum(c[0] for c in cross), cross_terms=sum(c[1] for c in cross),
                             declined=bool(re.search(r"(do not|don't|cannot|can't) (reliably )?(recall|remember)", text, re.I))))
            r = rows[-1]
            print(f"{model:18s} {pkg}  own {r['own_match']}/{r['own_terms']}  cross {r['cross_match']}/{r['cross_terms']}  "
                  f"numbers emitted {r['numbers_emitted']}  declined={r['declined']}", flush=True)
    (out / "probe.json").write_text(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()
