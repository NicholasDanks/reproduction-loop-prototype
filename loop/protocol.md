# Repair protocol (APPLY phase) — locked, from the pre-registered COMPVAL validation study

You are working inside a COPY of a research replication package. Your job is to make the package
reproduce its outputs on a clean machine by applying ONLY the changes listed as allowed below.
You have at most {minutes} minutes. Work only inside the current directory.

## Allowed (Level 1)
- Add a LICENSE file (MIT by default).
- Add or improve README.md with run instructions, Python/Stata version, and which script makes which output.
- Add or repair `requirements.txt` from the imports actually used. Pinning a version is allowed when a
  library's API has changed (for example, pin an older pandas if the code uses removed methods).
- Add `random.seed(...)` / `np.random.seed(...)` / `set seed` where randomness is used and no seed exists.
- Replace hardcoded absolute paths (drive letters, /Users/..., Dropbox paths) with paths relative to the script.
- Remove Jupyter `!pip install` magic (move it to requirements.txt).
- Add `plt.savefig()` where figures are produced but not saved.
- Create an `output/` directory if it is missing.
- Add a `run_all.py` or `run_all.sh` that runs the scripts in the right order.
- Replace a library call that no longer exists with its documented drop-in equivalent, when and only
  when the replacement is behaviour-preserving (for example `DataFrame.append` -> `pd.concat`).

## Allowed (Level 2)
- Turn wildcard imports into explicit imports.
- Add `if __name__ == "__main__":` guards.
- Add comments labelling which script produces which paper table or figure.

## Forbidden
- Changing analytical logic, formulae, estimators, or model specifications.
- Rewriting algorithms or restructuring the data flow.
- Adding analytical steps that were not in the original.
- Modifying, replacing, regenerating, or deleting anything under `data/`.
- Writing output files by hand, or hardcoding numbers. Outputs must come from running the code.
- Reading or using any file outside this directory.

## Procedure
1. Read README and the code. Identify the entry point: {entry}
2. Try to run it. Diagnose the first failure.
3. Apply the smallest allowed change that addresses it. Re-run. Repeat until it runs or the allowed
   list is exhausted or time is up.
4. Write `AGENT_REPORT.md` in this directory: what failed, what you changed and why, what still fails,
   and the exact command that runs the package. Do not claim success you did not observe.

Stop when the entry point runs to completion, or when you have nothing allowed left to try.
