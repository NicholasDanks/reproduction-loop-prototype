# Real MNSC packages for the loop

Six packages from the pre-registered n=25 repair study, chosen because their article PDF is on disk
and they span the outcome space: two the study repaired fully (22-03335, 23-02958), one Stata package
newly runnable now that Stata is installed (23-02078), one shipping a 96-byte data stub (23-04183),
one missing licensed data (24-05365), and one needing a solver we do not have (22-00832).

Each `real/<pkg>/` holds `stage.json` (source path in the COMPVAL corpus, entry point, notes),
`paper/manifest.json` (the article's claims: artifacts and, where the article prints numbers,
values with page references) and `SOURCE.md` (what was transcribed from which page, and caveats).
`python3 real/stage.py <pkg>` copies the package to `~/compval_real/<pkg>/` with `paper/` overlaid
and `.compval_entry` set; the loop withholds `paper/` from the agent as with the fixtures.

Ground truth caveats
- Value matching is presence-based: a value counts as reproduced if some produced text file contains
  a number that rounds to it at the stated digits. Two-decimal values (24-05365) are weak evidence.
- Figure-only articles (22-03335, 23-02958) are checked at artifact level only.
- Pre-shipped outputs (23-02078 figures, 22-00832 simulation/output) count only if overwritten.
- The strict baseline uses a fresh venv and installs only what the package declares. Packages with
  no requirements file fail at the first import; the 2026-05 study ran some of these against a
  system Python with numpy already present, so its strict numbers are not directly comparable.
