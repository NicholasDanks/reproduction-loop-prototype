"""Simulation study: generates the panel and reproduces Tables 1-2. Seed fixed at 719. Stdlib only."""
import csv, random
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
SEED = 719

def ols(y, X):
    """OLS by normal equations with Gaussian elimination. X: list of rows incl. intercept. Returns betas."""
    k = len(X[0]); XtX = [[sum(r[i]*r[j] for r in X) for j in range(k)] for i in range(k)]
    Xty = [sum(r[i]*yy for r, yy in zip(X, y)) for i in range(k)]
    A = [row[:] + [b] for row, b in zip(XtX, Xty)]
    for c in range(k):
        p = max(range(c, k), key=lambda r: abs(A[r][c])); A[c], A[p] = A[p], A[c]
        for r in range(k):
            if r != c:
                f = A[r][c]/A[c][c]; A[r] = [a - f*b for a, b in zip(A[r], A[c])]
    return [A[i][k]/A[i][i] for i in range(k)]

def analysis(rows):
    """Table 1 descriptives and Table 2 OLS: roa ~ adopted + size + age + year dummies."""
    years = sorted({r["year"] for r in rows}); base = years[0]
    y = [r["roa"] for r in rows]
    X = [[1.0, r["adopted"], r["size"], r["age"]] + [1.0 if r["year"] == yy else 0.0 for yy in years[1:]] for r in rows]
    b = ols(y, X); names = ["const", "adopted", "size", "age"] + [f"year_{yy}" for yy in years[1:]]
    t1 = [("n_obs", len(rows)), ("n_firms", len({r["firm"] for r in rows})),
          ("mean_roa", sum(y)/len(y)), ("share_adopted", sum(r["adopted"] for r in rows)/len(rows))]
    return t1, list(zip(names, b))

def assign_treatment(rng, n_firms):
    return [rng.choice([2019, 2020, 2021, 9999]) for _ in range(n_firms)]

def draw_firms(rng, n_firms, adopt_years, years=(2018, 2019, 2020, 2021, 2022)):
    rows = []
    for f in range(1, n_firms + 1):
        size = rng.gauss(5.0, 1.0); age0 = rng.randint(3, 40); firm_fe = rng.gauss(0, 0.5)
        for y in years:
            adopted = 1 if y >= adopt_years[f - 1] else 0
            year_fe = {2018: 0.0, 2019: 0.2, 2020: -0.6, 2021: 0.3, 2022: 0.4}[y]
            roa = 2.0 + 1.5*adopted + 0.8*size - 0.05*(age0 + y - 2018) + year_fe + firm_fe + rng.gauss(0, 1.0)
            rows.append(dict(firm=f, year=y, roa=roa, adopted=adopted, size=size, age=age0 + y - 2018))
    return rows

def main():
    rng = random.Random(SEED)
    adopt_years = assign_treatment(rng, 200)
    # --- PERTURBATION POINT: any extra draw from rng here changes every covariate below ---
    rows = draw_firms(rng, 200, adopt_years)
    t1, t2 = analysis(rows)
    (ROOT / "output").mkdir(exist_ok=True)
    with open(ROOT / "output" / "table1.csv", "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["statistic", "value"]); [w.writerow([k, f"{v:.6f}"]) for k, v in t1]
    with open(ROOT / "output" / "table2.csv", "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["term", "estimate"]); [w.writerow([k, f"{v:.6f}"]) for k, v in t2]
    print("wrote output/table1.csv and output/table2.csv")

if __name__ == "__main__":
    main()
