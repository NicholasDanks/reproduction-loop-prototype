# Fixture fx02_potemkin
**Planted property:** the shipped `data/panel.csv` is pseudo data (different generator seed). Code, README, licence and structure are identical to fx01. The README says the package "reproduces all tables"; it does not: every coefficient differs from `paper/table2.csv`.
**Expected as shipped:** runs, rc 0, all output files produced, ZERO values match the paper. This is what a binary "does it run" check passes and a value-level check fails. Modelled on corpus packages 22-02414 and 23-04183.
**Expected after protocol:** cannot be repaired without the real data. Verdict must be "runs but does not reproduce".
**Detection:** output-vs-paper comparison; a static scorer that credits "data included" is fooled (as our tool was on 21-01832).
