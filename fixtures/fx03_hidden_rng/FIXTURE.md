# Fixture fx03_hidden_rng
**Planted property:** a single RNG stream is consumed by two stages (treatment assignment, then covariate draws). Any extra draw between them silently changes every covariate and therefore Table 2. The code is correct; the dependency is undocumented. Modelled on corpus package M17 (Liu et al.), where one extra `rnorm(1)` dropped a correlation from 1.0 to -0.04.
**Expected as shipped:** runs, rc 0, values match `paper/` exactly.
**Expected under perturbation** (`python3 perturb.py`): values change. No static item in the instrument sees this; only a perturbation test does.
