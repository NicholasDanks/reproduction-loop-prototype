# Fixture fx05_stata_hardpath
**Planted property:** `code/main.do` opens with `cd "C:\Users\author\Dropbox\..."`, so it fails on any machine but the author's. Everything else is correct. Modelled on corpus package 23-00681 (`use "D:\cl\..."`), the single most common strict-reproduction failure in the corpus (instrument item A5.2).
**Expected as shipped:** r(170) at the `cd` line, no outputs. Strict 0%.
**Expected after a Level-1 fix** (delete the `cd` line, run from the package root): rc 0, Table 2 matches `paper/table2.csv` to 1e-5 (Stata's `regress` versus the fixtures' stdlib OLS; identical model).
**Detection:** static scorer catches the drive-letter pattern (A5.2) AND execution confirms it; this fixture is where static and dynamic checks agree.
