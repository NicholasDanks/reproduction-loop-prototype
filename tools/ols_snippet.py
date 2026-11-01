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
