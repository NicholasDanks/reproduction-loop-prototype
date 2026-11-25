#!/usr/bin/env python3
"""Run a Stata do-file in batch mode with a timeout and return a structured result.

Needs a licensed local Stata (path in STATA below); no licence file is in this repository. Usage:

    python3 stata_runner.py path/to/file.do [--cwd DIR] [--timeout SEC]

As a library:  from stata_runner import run_do; r = run_do("main.do", cwd=pkg_dir)
Result keys: rc (Stata return code parsed from log, 0 if none), exit (process exit), timed_out,
log (path), seconds, errors (list of 'r(NNN);' lines with the preceding command).
"""
import argparse, json, os, re, subprocess, sys, time
from pathlib import Path

STATA = "/Applications/Stata/StataMP.app/Contents/MacOS/stata-mp"

def run_do(dofile, cwd=None, timeout=900, env=None):
    dofile = Path(dofile).resolve(); cwd = Path(cwd or dofile.parent).resolve()
    # Stata's batch parser splits on spaces, so run through a wrapper do-file in cwd.
    wrapper = cwd / "_compval_run.do"
    wrapper.write_text(f'do "{dofile}"\n')
    log = cwd / "_compval_run.log"
    if log.exists(): log.unlink()
    t0 = time.time(); timed_out = False
    try:
        p = subprocess.run([STATA, "-b", "do", wrapper.name], cwd=cwd, timeout=timeout,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
        exit_code = p.returncode
    except subprocess.TimeoutExpired:
        timed_out = True; exit_code = None
    text = log.read_text(errors="replace") if log.exists() else ""
    wrapper.unlink(missing_ok=True)
    lines = text.splitlines(); errors = []; rc = 0
    for i, ln in enumerate(lines):
        m = re.fullmatch(r"r\((\d+)\);", ln.strip())
        if m:
            rc = int(m.group(1))
            prev = next((lines[j] for j in range(i-1, max(i-8, -1), -1) if lines[j].startswith(". ")), "")
            errors.append({"rc": rc, "command": prev.strip(), "message": lines[i-1].strip() if i else ""})
    return dict(dofile=str(dofile), cwd=str(cwd), log=str(log), exit=exit_code, rc=rc,
                timed_out=timed_out, seconds=round(time.time()-t0, 1), errors=errors,
                stata_licensed="License is invalid" not in text and "Cannot find license" not in text)

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("dofile"); ap.add_argument("--cwd"); ap.add_argument("--timeout", type=int, default=900)
    a = ap.parse_args(); print(json.dumps(run_do(a.dofile, a.cwd, a.timeout), indent=2))
