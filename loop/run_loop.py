#!/usr/bin/env python3
"""AI reproduction loop under a locked protocol, with pluggable agent backends.

  python3 loop/run_loop.py --package fixtures/fx04_api_drift --backend claude [--model M] [--repeats 3]
  python3 loop/run_loop.py --package fixtures/fx05_stata_hardpath --backend none

Phases (BEFORE and AFTER are deterministic and agent-free; APPLY is the agent):
  BEFORE  copy package, withhold paper/, fresh venv, install requirements, run entry, classify first failure
  APPLY   hand loop/protocol.md to the backend inside the copy; time-capped; diff recorded; forbidden-change check
  AFTER   fresh venv, rerun entry, compare outputs to the withheld paper tables by term
Writes runs/<package>/<backend>/<model>/rep<k>/{report.json, changes.diff, agent_stdout.txt, agent_stream.jsonl, work/}.
Isolation (15 Oct 2026): the agent works in a copy under ISO_ROOT (/private/tmp, outside $HOME and outside any git
repo; Claude Code loads ~/.claude/CLAUDE.md for any cwd under $HOME), the withheld paper stays in the run dir, and
every Claude run is checked from its raw stream: init record (no skills, MCP servers or slash commands; exactly six
tools), served model == requested model, no tool input touching the withheld paper or the author's home.
"""
import argparse, json, os, re, shutil, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from compare import compare

ROOT = Path(__file__).resolve().parent.parent
COMPVAL = Path(os.environ.get("COMPVAL_DIR", ROOT / "core"))
BACKENDS = json.load(open(ROOT / "loop" / "backends.json"))
STATA = Path("/Applications/Stata/StataMP.app/Contents/MacOS/stata-mp")
ISO_ROOT = Path(os.environ.get("COMPVAL_ISO_ROOT", "/private/tmp/compval_work"))   # agent work copies live here, outside $HOME
WANT_TOOLS = {"Bash", "Edit", "Glob", "Grep", "Read", "Write"}
AGENT_ENV = {**os.environ, "CLAUDECODE": "", "PATH": str(STATA.parent) + ":" + os.environ.get("PATH", "")}

# Stata isolation (20 Oct 2026): every phase gets empty PLUS/PERSONAL/OLDPLACE folders. profile.do in the package
# root redirects installs (Stata runs it from the working directory, batch mode included); S_ADO pins the search path
# to the phase folder even if Stata is launched from elsewhere. Without this, ados left in the host's global PLUS
# folder by earlier runs made 23-02078 reproduce (replay_23-02078_2026-10-20/RESULT.md).
def stata_phase(pkg, phase_root):
    for d in ("plus", "personal", "oldplace"): (phase_root / d).mkdir(parents=True, exist_ok=True)
    (pkg / "profile.do").write_text("".join(f'sysdir set {k.upper()} "{phase_root / k}"\n' for k in ("plus", "personal", "oldplace")))
    return {**AGENT_ENV, "S_ADO": f"BASE;SITE;.;{phase_root / 'personal'};{phase_root / 'plus'}"}

# R (21 Oct 2026, after the first Org Sci batch): each run wipes the package's own library, so a declared R dependency
# file is installed into it before the entry runs, as requirements.txt is for Python. During APPLY the agent's R
# installs default to that library, and any write to the host library is flagged (two agents installed there).
R_DEP_FILES = ("requirements.R", "install_packages.R", "install.R", "install_deps.R", "dependencies.R")
def host_r_library():
    """Host R packages -> DESCRIPTION change time; empty if R is absent."""
    try: lib = subprocess.run(["Rscript", "--no-init-file", "-e", "cat(.Library)"], capture_output=True, text=True, timeout=60, env=os.environ).stdout.strip()
    except (OSError, subprocess.TimeoutExpired): return {}
    return {d.name: (d / "DESCRIPTION").stat().st_ctime for d in Path(lib).iterdir() if (d / "DESCRIPTION").exists()} if lib else {}

def save_console(pkg, name, out):
    """Keep what the run printed (21 Oct 2026): R and Python tables often go only to the console (stargazer, print),
    as Stata's do in its log. Partial output survives a timeout."""
    if isinstance(out, bytes): out = out.decode("utf-8", "replace")
    if out and out.strip(): (pkg / name).write_text(out)

# ---------------- entry detection & execution ----------------
def detect_entry(pkg):
    if (pkg / ".compval_entry").exists(): return (pkg / ".compval_entry").read_text().strip()
    for c in ["run_all.py", "run_all.sh", "code/run.py", "code/main.do", "code/main.py", "main.py", "master.do", "main.do", "run.py",
              "main.R", "master.R", "run_all.R"]:
        if (pkg / c).exists(): return c
    cands = sorted([p for p in pkg.rglob("*") if p.suffix in (".py", ".do", ".R", ".r") and ".venv" not in p.parts], key=lambda p: (len(p.parts), p.name))
    return str(cands[0].relative_to(pkg)) if cands else None

FAILURE_PATTERNS = [
    ("hardcoded-path", r"r\(170\)|No such file or directory: '[A-Z]:|[A-Z]:\\\\|/Users/[a-z]+/|Dropbox|r\(601\)|cannot change working directory"),
    ("missing-dep", r"ModuleNotFoundError|No module named|r\(199\)|command .* is unrecognized|there is no package called"),
    ("version-mismatch", r"AttributeError: .* has no attribute|TypeError: .* got an unexpected keyword|DeprecationWarning|FutureWarning"),
    ("missing-data", r"FileNotFoundError|file .* not found|No such file"),
    ("syntax-error", r"SyntaxError|invalid syntax|r\(198\)"),
    ("jupyter-magic", r"!pip|%matplotlib|get_ipython"),
]
def classify(text):
    for name, pat in FAILURE_PATTERNS:
        if re.search(pat, text): return name
    return "other" if text.strip() else "none"

def run_entry(pkg, entry, timeout=900, fresh_env=True, env=None):
    """Runs the entry point in a fresh venv (python) or Stata batch. Returns dict."""
    t0 = time.time(); (pkg / "output").mkdir(exist_ok=True)
    before_files = {p: p.stat().st_mtime for p in pkg.rglob("*") if p.is_file()}
    if entry.endswith(".do"):
        if not STATA.exists(): return dict(rc=None, error="Stata not installed", failure="blocked-commercial", seconds=0, outputs=[])
        sys.path.insert(0, str(COMPVAL)); from stata_runner import run_do
        r = run_do(pkg / entry, cwd=pkg, timeout=timeout, env=env)
        err = r["errors"][0]["command"] + " | " + r["errors"][0]["message"] if r["errors"] else ""
        rc = r["rc"]; log_tail = err
        if Path(r["log"]).exists(): shutil.copy(r["log"], pkg / "stata_batch_output.txt")   # esttab/di output lives in the log
    elif entry.endswith((".R", ".r")):
        # R (added 21 Oct 2026). The host R keeps every installed package in its base library, which env vars cannot
        # hide, so R runs are NOT isolated like Stata. Each run gets a fresh first library (installs go there) and the
        # wrapper records every non-base namespace loaded from the host: these are reported as host_dependencies.
        rlib = pkg / ".venv_rlib"; shutil.rmtree(rlib, ignore_errors=True); rlib.mkdir()
        (pkg / "_compval_run.R").write_text(
            'local({ base <- rownames(installed.packages(priority = c("base", "recommended")))\n'
            '  reg.finalizer(globalenv(), function(e) { ns <- loadedNamespaces()\n'
            '    p <- vapply(ns, function(n) tryCatch(getNamespaceInfo(n, "path"), error = function(e) NA_character_), "")\n'
            '    writeLines(paste(ns, p, ns %in% base, sep = "\\t"), "_compval_rpkgs.tsv") }, onexit = TRUE) })\n'
            f'source({json.dumps(entry)}, echo = FALSE, print.eval = TRUE)\n')   # print.eval: autoprint as Rscript does
        renv = {**(env or AGENT_ENV), "R_LIBS_USER": str(rlib), "R_LIBS": str(rlib)}
        dep = next((f for f in R_DEP_FILES if (pkg / f).exists()), None)
        if dep:
            try: ip = subprocess.run(["Rscript", "--no-init-file", dep], cwd=pkg, capture_output=True, text=True, timeout=timeout, env=renv)
            except subprocess.TimeoutExpired:
                return dict(rc=None, error=f"{dep} timed out", failure="missing-dep", seconds=round(time.time()-t0, 1), outputs=[], r_dep_file=dep)
            if ip.returncode != 0:
                return dict(rc=ip.returncode, error=f"{dep} failed: " + ip.stderr[-300:], failure="missing-dep", seconds=round(time.time()-t0, 1), outputs=[], r_dep_file=dep)
        try:
            p = subprocess.run(["Rscript", "--no-init-file", "_compval_run.R"], cwd=pkg, capture_output=True, text=True, timeout=timeout, env=renv)
            rc = p.returncode; log_tail = p.stderr[-2000:]; save_console(pkg, "r_console_output.txt", p.stdout)
        except subprocess.TimeoutExpired as e:
            save_console(pkg, "r_console_output.txt", e.stdout)
            return dict(rc=None, error="timeout", failure="timeout", seconds=round(time.time()-t0, 1), r_dep_file=dep,
                        outputs=["r_console_output.txt"] if (pkg / "r_console_output.txt").exists() else [])
    elif entry.endswith(".sh"):
        try:
            p = subprocess.run(["bash", entry], cwd=pkg, capture_output=True, text=True, timeout=timeout, env=AGENT_ENV); rc = p.returncode; log_tail = p.stderr[-2000:]
        except subprocess.TimeoutExpired:
            return dict(rc=None, error="timeout", failure="timeout", seconds=round(time.time()-t0, 1), outputs=[])
    elif entry.endswith(".ipynb"):
        venv = pkg / ".venv_run"; shutil.rmtree(venv, ignore_errors=True)
        subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True, capture_output=True); py = venv / "bin" / "python"
        reqs = ["nbconvert", "nbclient", "ipykernel"]
        if (pkg / "requirements.txt").exists(): reqs += ["-r", "requirements.txt"]
        ip = subprocess.run([str(py), "-m", "pip", "install", "-q"] + reqs, cwd=pkg, capture_output=True, text=True, timeout=timeout)
        if ip.returncode != 0:
            return dict(rc=ip.returncode, error="pip install failed: " + ip.stderr[-300:], failure="missing-dep", seconds=round(time.time()-t0, 1), outputs=[])
        try:
            p = subprocess.run([str(py), "-m", "nbconvert", "--to", "notebook", "--execute", "--ExecutePreprocessor.kernel_name=python3",
                                f"--ExecutePreprocessor.timeout={timeout}", "--output", "_executed.ipynb", entry], cwd=pkg, capture_output=True, text=True, timeout=timeout)
            rc = p.returncode; log_tail = p.stderr[-3000:]
        except subprocess.TimeoutExpired:
            return dict(rc=None, error="timeout", failure="timeout", seconds=round(time.time()-t0, 1), outputs=[])
    else:
        venv = pkg / ".venv_run"; shutil.rmtree(venv, ignore_errors=True)
        subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True, capture_output=True)
        py = venv / "bin" / "python"; install_log = ""
        req = next((r for r in [pkg / "requirements.txt", (pkg / entry).parent / "requirements.txt"] if r.exists()), None)
        if req:
            reqs = [l.strip() for l in req.read_text().splitlines() if l.strip() and not l.startswith("#")]
            if reqs:
                ip = subprocess.run([str(py), "-m", "pip", "install", "-q", "-r", str(req)], cwd=pkg, capture_output=True, text=True, timeout=timeout)
                install_log = ip.stderr[-1500:]
                if ip.returncode != 0:
                    return dict(rc=ip.returncode, error="pip install failed: " + install_log[-300:], failure="missing-dep", seconds=round(time.time()-t0, 1), outputs=[])
        try:
            p = subprocess.run([str(py), entry], cwd=pkg, capture_output=True, text=True, timeout=timeout); rc = p.returncode; log_tail = p.stderr[-2000:]
            save_console(pkg, "python_console_output.txt", p.stdout)
        except subprocess.TimeoutExpired as e:
            save_console(pkg, "python_console_output.txt", e.stdout)
            return dict(rc=None, error="timeout", failure="timeout", seconds=round(time.time()-t0, 1),
                        outputs=["python_console_output.txt"] if (pkg / "python_console_output.txt").exists() else [])
    def _skip(p): return any(part.startswith(".venv") or "venv" in part.lower() or part in ("__pycache__", "site-packages", ".ipynb_checkpoints", "env", ".git") for part in p.parts) or p.name in ("_compval_run.do", ".compval_entry", "profile.do", "_compval_run.R", "_compval_rpkgs.tsv")
    # .log files count: Stata batch logs carry esttab output (manifest "files" may name *.log). Empty files do not count:
    # a script that opens its output files and then dies leaves zero-byte artifacts (22-00832, 23-04183 on 17 Sep).
    outputs = sorted(str(p.relative_to(pkg)) for p in pkg.rglob("*") if p.is_file() and not _skip(p) and p.suffix != ".pyc"
                     and p.name != "_compval_run.log" and p.stat().st_size > 0
                     and (p not in before_files or p.stat().st_mtime > before_files[p]))
    err_line = (log_tail.strip().splitlines() or [""])[-1][:200]
    fail = "none" if not rc else (classify(err_line) if classify(err_line) != "other" else classify(log_tail))
    res = dict(rc=rc, error=err_line, failure=fail, seconds=round(time.time()-t0, 1), outputs=outputs)
    if entry.endswith((".R", ".r")): res["r_dep_file"] = dep
    tsv = pkg / "_compval_rpkgs.tsv"
    if tsv.exists():   # R: non-base packages the run loaded from the host library rather than its own
        rows = [l.split("\t") for l in tsv.read_text().splitlines() if l.count("\t") == 2]
        res["host_dependencies"] = sorted(n for n, path, isbase in rows if isbase == "FALSE" and not path.startswith(str(pkg)))
    return res

# ---------------- backends ----------------
def prompt_text(entry, minutes):
    return (ROOT / "loop" / "protocol.md").read_text().replace("{minutes}", str(minutes)).replace("{entry}", entry or "not obvious; find it")

def render_stream(raw):
    """Turn Claude Code stream-json (one JSON object per line) into a readable tool log; pass other text through."""
    lines = []; any_json = False
    for ln in raw.splitlines():
        try: ev = json.loads(ln)
        except Exception: lines.append(ln); continue
        any_json = True
        for blk in (ev.get("message", {}) or {}).get("content", []) if isinstance(ev.get("message"), dict) else []:
            if blk.get("type") == "text": lines.append(f"[assistant] {blk['text'][:1500]}")
            elif blk.get("type") == "tool_use": lines.append(f"[tool {blk.get('name')}] {json.dumps(blk.get('input'))[:400]}")
            elif blk.get("type") == "tool_result":
                c = blk.get("content"); c = c if isinstance(c, str) else json.dumps(c); lines.append(f"[result] {c[:500]}")
        if ev.get("type") == "result": lines.append(f"[result-summary] turns={ev.get('num_turns')} cost_usd={ev.get('total_cost_usd')} {str(ev.get('result',''))[:800]}")
    return "\n".join(lines) if any_json else raw

# Bash sandbox for APPLY (22 Oct 2026, after agents wrote to the host R library on 21 Oct). Seatbelt on macOS; covers
# every process an agent command starts. Writes: the work copy, the per-user temp dir and the APPLY Stata folder
# (not orig/, the diff baseline beside it). Reads: the home directory is denied. Network: package registries
# only. No unsandboxed retry; the run fails if the sandbox cannot start. The file tools (Read/Edit/Write) are outside
# the sandbox and stay governed by the tool allowlist and the copy living outside $HOME.
SANDBOX_DOMAINS = ["cloud.r-project.org", "cran.r-project.org", "cran.rstudio.com", "pypi.org", "files.pythonhosted.org",
                   "fmwww.bc.edu", "www.stata.com", "github.com", "codeload.github.com", "raw.githubusercontent.com",
                   "objects.githubusercontent.com"]
def sandbox_settings(pkg):
    return json.dumps({"sandbox": {"enabled": True, "failIfUnavailable": True, "allowUnsandboxedCommands": False,
                                   "autoAllowBashIfSandboxed": False,
                                   "filesystem": {"allowWrite": [str(Path(pkg).parent / "stata_apply")], "denyRead": ["~/"]},
                                   "network": {"allowedDomains": SANDBOX_DOMAINS}}})

def run_cli_backend(spec, model, pkg, prompt, cap):
    cmd = [c.replace("{model}", model).replace("{prompt}", prompt).replace("{sandbox}", sandbox_settings(pkg)) for c in spec["cmd"]]
    t0 = time.time()
    try:
        p = subprocess.run(cmd, cwd=pkg, capture_output=True, text=True, timeout=cap, env=AGENT_ENV)
        raw = p.stdout
        out, rc, to = render_stream(raw) + "\n--- stderr ---\n" + p.stderr[-3000:], p.returncode, False
    except subprocess.TimeoutExpired as e:
        raw = (e.stdout or b"").decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        out, rc, to = render_stream(raw), None, True   # rendered, so tool calls are counted on timeouts too
    return dict(stdout=out, raw=raw, rc=rc, timed_out=to, seconds=round(time.time()-t0, 1), turns=None)

def check_stream(raw, want_model):
    """Isolation and model check from a Claude Code stream-json log (same standard as AI_phd_student's
    check_clean.py / check_model.py). problems => the run is not admissible and the batch stops."""
    init, served, first, problems, flags = None, set(), None, [], []
    sensitive = ["paper_withheld", "compval_real", "compval_runs", "FIXTURE", "research_journal", str(Path.home()), ".claude/"]
    for ln in raw.splitlines():
        try: m = json.loads(ln)
        except ValueError: continue
        if m.get("type") == "system" and m.get("subtype") == "init" and init is None:
            init = {k: m.get(k) for k in ("claude_code_version", "model", "cwd", "tools", "mcp_servers", "skills", "slash_commands", "plugins")}
        if m.get("type") == "assistant":
            msg = m.get("message") or {}; served.add(msg.get("model"))
            if first is None:
                u = msg.get("usage") or {}; first = sum(u.get(k) or 0 for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
            for c in msg.get("content") or []:
                if c.get("type") == "tool_use":
                    blob = json.dumps(c.get("input"))
                    problems += [f"tool input references {t}: {blob[:120]}" for t in sensitive if t in blob]
                    if "manifest.json" in blob: flags.append(f"manifest.json in a tool input: {blob[:120]}")
    served.discard(None)
    if init is None: problems.append("no init record")
    else:
        if init.get("skills"): problems.append(f"skills={len(init['skills'])}")
        if init.get("mcp_servers"): problems.append("mcp=" + ",".join(s.get("name", "?") for s in init["mcp_servers"]))
        if init.get("slash_commands"): problems.append(f"slash_commands={len(init['slash_commands'])}")
        if set(init.get("tools") or []) != WANT_TOOLS: problems.append(f"tools={sorted(init.get('tools') or [])}")
        if not str(init.get("cwd") or "").startswith(str(ISO_ROOT)): problems.append(f"cwd={init.get('cwd')}")
    if served != {want_model}: problems.append(f"served={sorted(served)} want={want_model}")
    return dict(clean=not problems, problems=problems, flags=flags, served=sorted(served), init=init, first_call_prompt_tokens=first)

def harness_commit():
    h = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain", "--", "loop"], capture_output=True, text=True).stdout.strip()
    return (h or "unknown") + ("-dirty" if dirty else "")

TOOLS = [
 {"type": "function", "function": {"name": "list_files", "description": "List files under the package (relative paths).", "parameters": {"type": "object", "properties": {}}}},
 {"type": "function", "function": {"name": "read_file", "description": "Read a text file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
 {"type": "function", "function": {"name": "write_file", "description": "Write a text file (creates or overwrites).", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
 {"type": "function", "function": {"name": "run_command", "description": "Run a shell command in the package directory (120 s cap). Returns stdout+stderr.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
]
def tool_exec(pkg, name, args):
    try:
        if name == "list_files":
            return "\n".join(sorted(str(p.relative_to(pkg)) for p in pkg.rglob("*") if p.is_file() and not any(x.startswith(".venv") for x in p.parts)))[:8000]
        if name == "read_file":
            fp = (pkg / args["path"]).resolve(); assert str(fp).startswith(str(pkg.resolve())), "outside package"
            return fp.read_text(errors="replace")[:20000]
        if name == "write_file":
            fp = (pkg / args["path"]).resolve(); assert str(fp).startswith(str(pkg.resolve())), "outside package"
            if "data/" in args["path"].replace("\\", "/"): return "REFUSED: data/ is read-only under the protocol"
            fp.parent.mkdir(parents=True, exist_ok=True); fp.write_text(args["content"]); return f"wrote {args['path']}"
        if name == "run_command":
            p = subprocess.run(args["command"], shell=True, cwd=pkg, capture_output=True, text=True, timeout=120, env=AGENT_ENV)
            return (p.stdout + p.stderr)[-6000:] or f"(exit {p.returncode}, no output)"
    except Exception as e:
        return f"ERROR: {e}"
    return "unknown tool"

def run_openai_backend(spec, model, pkg, prompt, cap, max_turns=150):
    base = os.path.expandvars(spec["base_url"]); key = os.environ.get(spec.get("api_key_env") or "", "ollama")
    msgs = [{"role": "system", "content": "You are a careful research-software engineer. Use the tools. Follow the protocol exactly."}, {"role": "user", "content": prompt}]
    t0 = time.time(); log = []; turns = 0
    while turns < max_turns and time.time() - t0 < cap:
        body = json.dumps({"model": model, "messages": msgs, "tools": TOOLS, "temperature": 0.2}).encode()
        req = urllib.request.Request(base.rstrip("/") + "/chat/completions", data=body, headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
        try:
            with urllib.request.urlopen(req, timeout=max(30, cap - (time.time() - t0))) as r: resp = json.load(r)
        except Exception as e:
            log.append(f"API error: {e}"); break
        msg = resp["choices"][0]["message"]; msgs.append(msg); turns += 1
        calls = msg.get("tool_calls") or []
        if msg.get("content"): log.append(f"[assistant] {msg['content'][:1500]}")
        if not calls: break
        for c in calls:
            fn = c["function"]["name"]; 
            try: args = json.loads(c["function"].get("arguments") or "{}")
            except json.JSONDecodeError: args = {}
            res = tool_exec(pkg, fn, args); log.append(f"[tool {fn}] {json.dumps(args)[:300]} -> {res[:500]}")
            msgs.append({"role": "tool", "tool_call_id": c.get("id", fn), "content": res})
    return dict(stdout="\n".join(log), rc=0, timed_out=time.time() - t0 >= cap, seconds=round(time.time()-t0, 1), turns=turns)

# ---------------- forbidden-change check ----------------
ANALYTIC = re.compile(r"\b(regress|xtreg|areg|reghdfe|ivreg2?|logit|probit|lstsq|OLS\(|sm\.|statsmodels|lm\(|glm\(|felm|feols|np\.linalg)\b|formula\s*=", re.I)
def make_diff(orig, work):
    p = subprocess.run(["diff", "-ruN", "-x", "profile.do", "-x", ".venv*", "-x", "output", "-x", "*.log", "-x", "__pycache__", "-x", "_compval_run.do", "-x", "_compval_run.R", "-x", "_compval_rpkgs.tsv", "-x", "stata_batch_output.txt", "-x", "r_console_output.txt", "-x", "python_console_output.txt", "-x", "_executed.ipynb", "-x", ".compval_entry", "-x", "*venv*", "-x", "env", "-x", ".git", "-x", "site-packages", str(orig), str(work)], capture_output=True)
    raw = p.stdout; d = raw.decode("utf-8", "replace"); flags = []   # bytes: text mode dropped CR from CRLF files (20 Oct)
    if re.search(r"^diff .*?/data/", d, re.M): flags.append("data/ modified")
    changed = [l[1:] for l in d.splitlines() if (l.startswith("+") or l.startswith("-")) and not l.startswith(("+++", "---"))]
    if any(ANALYTIC.search(l) for l in changed): flags.append("analytic keyword in changed lines (human review)")
    if re.search(r"^diff .*?/output/", d, re.M): flags.append("output/ written by hand")
    return raw, d, flags, len(changed)

# ---------------- main ----------------
def one_run(src, backend, model, rep, out_root, entry, cap_apply, cap_run):
    spec = BACKENDS[backend]; model = model or spec.get("default_model", "")
    run_dir = out_root / src.name / backend / (model.replace("/", "_").replace(":", "_") or "none") / f"rep{rep}"
    if run_dir.exists(): shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True); ISO_ROOT.mkdir(parents=True, exist_ok=True)
    iso = Path(tempfile.mkdtemp(prefix="w_", dir=ISO_ROOT))   # agent's copy: outside $HOME, away from the withheld paper
    work = iso / "work"; orig = iso / "orig"; paper_hold = run_dir / "paper_withheld"
    shutil.copytree(src, work, ignore=shutil.ignore_patterns(".venv*", "__pycache__", "*.log", "_compval_run.do", "perturb.py"))
    if (work / "paper").exists(): shutil.move(str(work / "paper"), str(paper_hold))
    else: paper_hold.mkdir()
    (work / "FIXTURE.md").unlink(missing_ok=True)   # never show the agent the planted-defect note
    if (src / "output").exists(): shutil.rmtree(work / "output", ignore_errors=True); (work / "output").mkdir(exist_ok=True)
    shutil.copytree(work, orig)
    entry = entry or detect_entry(work)
    is_stata = bool(entry) and entry.endswith(".do"); is_r = bool(entry) and entry.endswith((".R", ".r"))
    if is_stata and (src / "profile.do").exists(): raise SystemExit(f"{src.name} ships its own profile.do; Stata isolation would overwrite it")
    def phase_env(name): return stata_phase(work, iso / f"stata_{name}") if is_stata else None
    report = dict(package=src.name, backend=backend, model=model, rep=rep, entry=entry, protocol_sha=None, started=time.strftime("%Y-%m-%dT%H:%M:%S"),
                  harness_commit=harness_commit(), work_dir_during_run=str(work), stata_isolated=is_stata)
    # BEFORE
    report["before"] = run_entry(work, entry, cap_run, env=phase_env("before")) if entry else dict(rc=None, failure="no-entry", outputs=[], seconds=0, error="")
    report["before"]["compare"] = compare(work, paper_hold, outputs=report["before"].get("outputs", []))
    shutil.rmtree(work / ".venv_run", ignore_errors=True)
    # APPLY
    apply_profile = (work / "profile.do").read_text() if is_stata and (work / "profile.do").exists() else None
    if spec["type"] == "noop": report["apply"] = dict(stdout="", rc=0, timed_out=False, seconds=0, turns=0)
    else:
        prompt = prompt_text(entry, cap_apply // 60)
        apply_env = phase_env("apply"); apply_profile = (work / "profile.do").read_text() if is_stata else None
        if apply_env: AGENT_ENV["S_ADO"] = apply_env["S_ADO"]
        if is_r:
            (work / ".venv_rlib").mkdir(exist_ok=True); AGENT_ENV["R_LIBS_USER"] = AGENT_ENV["R_LIBS"] = str(work / ".venv_rlib")
        host_before = host_r_library() if is_r else {}
        try: report["apply"] = (run_cli_backend if spec["type"] == "cli" else run_openai_backend)(spec, model, work, prompt, cap_apply)
        finally:
            AGENT_ENV.pop("S_ADO", None); AGENT_ENV.pop("R_LIBS_USER", None); AGENT_ENV.pop("R_LIBS", None)
            if "R_LIBS_USER" in os.environ: AGENT_ENV["R_LIBS_USER"] = os.environ["R_LIBS_USER"]
            if "R_LIBS" in os.environ: AGENT_ENV["R_LIBS"] = os.environ["R_LIBS"]
        if is_r:
            host_after = host_r_library()
            report["apply"]["host_r_library_written"] = sorted(k for k in host_after if host_before.get(k) != host_after[k])
    _out = report["apply"].pop("stdout", ""); (run_dir / "agent_stdout.txt").write_text(_out)
    _raw = report["apply"].pop("raw", None)
    if _raw is not None:
        (run_dir / "agent_stream.jsonl").write_text(_raw)
        report["apply"]["checks"] = check_stream(_raw, model)
    report["apply"]["tool_calls"] = len(re.findall(r"^\[tool ", _out, re.M))
    report["apply"]["denied_calls"] = len(re.findall(r"requires approval|permission denied|not allowed", _out, re.I))
    report["apply"]["exec_calls"] = len(re.findall(r"^\[tool (Bash|run_command)\]", _out, re.M))
    raw_diff, diff, flags, nlines = make_diff(orig, work); (run_dir / "changes.diff").write_bytes(raw_diff)
    if is_stata and ((work / "profile.do").read_text() if (work / "profile.do").exists() else None) != apply_profile:
        flags.append("agent altered the Stata isolation profile.do")
    if report["apply"].get("host_r_library_written"): flags.append("agent wrote to the host R library: " + ", ".join(report["apply"]["host_r_library_written"]))
    report["apply"].update(dict(changed_lines=nlines, flags=flags, agent_report=(work / "AGENT_REPORT.md").read_text()[:4000] if (work / "AGENT_REPORT.md").exists() else None))
    # AFTER
    entry_after = "run_all.py" if (work / "run_all.py").exists() else ("run_all.sh" if (work / "run_all.sh").exists() else entry)
    report["after"] = run_entry(work, entry_after, cap_run, env=phase_env("after")) if entry_after else dict(rc=None, failure="no-entry", outputs=[], seconds=0, error="")
    report["after"]["entry"] = entry_after; report["after"]["compare"] = compare(work, paper_hold, outputs=report["after"].get("outputs", []))
    shutil.rmtree(work / ".venv_run", ignore_errors=True)
    shutil.move(str(work), str(run_dir / "work")); shutil.move(str(orig), str(run_dir / "orig")); shutil.rmtree(iso, ignore_errors=True)
    (run_dir / "report.json").write_text(json.dumps(report, indent=2))
    b, a = report["before"], report["after"]
    def fmt(c): return f"{c['n_match']}/{c['n_terms']}" + (f" claims {c['claims_produced']}/{c['claims_total']}" if c.get('claims_total') is not None else "")
    print(f"{src.name:22s} {backend:8s} {model[:22]:22s} rep{rep}  BEFORE rc={b['rc']} {fmt(b['compare'])} [{b['failure']}]  "
          f"AFTER rc={a['rc']} {fmt(a['compare'])} [{a['failure']}]  apply {report['apply']['seconds']}s lines={nlines} flags={flags}")
    ck = report["apply"].get("checks")
    if ck: print(f"    checks: {'CLEAN' if ck['clean'] else 'DIRTY ' + '; '.join(ck['problems'])}  served={ck['served']}  cli={(ck['init'] or {}).get('claude_code_version')}  first-call tokens={ck['first_call_prompt_tokens']}")
    return report

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--package", required=True); ap.add_argument("--backend", default="none", choices=list(BACKENDS))
    ap.add_argument("--model"); ap.add_argument("--repeats", type=int, default=1); ap.add_argument("--entry"); ap.add_argument("--out", default=os.environ.get("COMPVAL_RUNS", str(Path.home() / "compval_runs")), help="work copies must live OUTSIDE any git repo (agents can otherwise read the fixtures/tests via git)")
    ap.add_argument("--cap-apply", type=int, default=1800); ap.add_argument("--cap-run", type=int, default=900)
    ap.add_argument("--rep", type=int, help="explicit rep number (overwrites that rep); default: next free rep")
    a = ap.parse_args()
    out = Path(a.out).resolve(); out.mkdir(parents=True, exist_ok=True)
    if subprocess.run(["git", "-C", str(out), "rev-parse", "--show-toplevel"], capture_output=True).returncode == 0:
        sys.exit(f"refusing: {out} is inside a git repository; agents could read it. Use --out outside any repo.")
    src = Path(a.package).resolve(); model = a.model or BACKENDS[a.backend].get("default_model", "")
    mdir = out / src.name / a.backend / (model.replace("/", "_").replace(":", "_") or "none")
    existing = [int(d.name[3:]) for d in mdir.glob("rep*") if d.name[3:].isdigit()] if mdir.exists() else []
    first = a.rep if a.rep else (max(existing) + 1 if existing else 1)   # never overwrite an earlier rep unless --rep says so
    for rep in range(first, first + a.repeats):
        r = one_run(src, a.backend, a.model, rep, out, a.entry, a.cap_apply, a.cap_run)
        ck = r["apply"].get("checks")
        if ck and not ck["clean"]: sys.exit(f"ISOLATION/MODEL CHECK FAILED for {src.name} rep{rep}: " + "; ".join(ck["problems"]))

if __name__ == "__main__":
    main()
