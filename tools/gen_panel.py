"""Deterministic synthetic firm panel used by the fixtures. Stdlib only.

200 firms x 5 years. Outcome roa; staggered treatment adopted; covariates size, age.
True model: roa = 2.0 + 1.5*adopted + 0.8*size - 0.05*age + year effects + noise.
"""
import csv, random, sys

def make_panel(seed=20260912, n_firms=200, years=(2018, 2019, 2020, 2021, 2022)):
    rng = random.Random(seed); rows = []
    for f in range(1, n_firms + 1):
        size = rng.gauss(5.0, 1.0); age0 = rng.randint(3, 40)
        adopt_year = rng.choice([2019, 2020, 2021, 9999])
        firm_fe = rng.gauss(0, 0.5)
        for y in years:
            adopted = 1 if y >= adopt_year else 0
            year_fe = {2018: 0.0, 2019: 0.2, 2020: -0.6, 2021: 0.3, 2022: 0.4}[y]
            roa = 2.0 + 1.5*adopted + 0.8*size - 0.05*(age0 + y - 2018) + year_fe + firm_fe + rng.gauss(0, 1.0)
            rows.append(dict(firm=f, year=y, roa=round(roa, 6), adopted=adopted, size=round(size, 6), age=age0 + y - 2018))
    return rows

def write(rows, path):
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

if __name__ == "__main__":
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 20260912
    write(make_panel(seed), sys.argv[1]); print("wrote", sys.argv[1], "seed", seed)
