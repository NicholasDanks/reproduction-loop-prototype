# Fixture fx04_api_drift
**Planted property:** `requirements.txt` is unpinned and the code uses two pandas 1.x APIs removed in pandas 2.0 (`DataFrame.append`, `DataFrame.iteritems`). Installing today's pandas gives `AttributeError`. The README's "tested in 2021" is the only clue. Modelled on the 6/25 API-drift packages in the repair study (pandas, numpy ABI, scipy/IPython, patsy).
**Expected as shipped (current pandas):** install succeeds, run fails, rc != 0, no outputs. Strict 0%.
**Expected after a Level-2 fix** (pin `pandas<2` in requirements, or replace the two calls): runs and matches `paper/` to 1e-5.
**Detection:** static scorer sees a requirements file and credits it (A3.2); only execution reveals the drift. Pin tightening (not relaxing) is the fix here, cf. corpus package 19-03211.
