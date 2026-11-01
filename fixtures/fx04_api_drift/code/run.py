"""Reproduces Tables 1-2 with pandas/numpy. Written against pandas 1.x (2021)."""
import numpy as np, pandas as pd
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent

def main():
    df = pd.read_csv(ROOT / "data" / "panel.csv")
    # Table 1 (built row by row with DataFrame.append, the pandas 1.x idiom)
    t1 = pd.DataFrame(columns=["statistic", "value"])
    t1 = t1.append({"statistic": "n_obs", "value": len(df)}, ignore_index=True)
    t1 = t1.append({"statistic": "n_firms", "value": df.firm.nunique()}, ignore_index=True)
    t1 = t1.append({"statistic": "mean_roa", "value": df.roa.mean()}, ignore_index=True)
    t1 = t1.append({"statistic": "share_adopted", "value": df.adopted.mean()}, ignore_index=True)
    # Table 2: OLS with year dummies
    yd = pd.get_dummies(df.year, prefix="year", drop_first=True).astype(float)
    X = pd.concat([pd.Series(1.0, index=df.index, name="const"), df[["adopted", "size", "age"]].astype(float), yd], axis=1)
    beta, *_ = np.linalg.lstsq(X.values, df.roa.values, rcond=None)
    rows = [(name, b) for (name, _), b in zip(X.iteritems(), beta)]
    (ROOT / "output").mkdir(exist_ok=True)
    t1.to_csv(ROOT / "output" / "table1.csv", index=False, float_format="%.6f")
    pd.DataFrame(rows, columns=["term", "estimate"]).to_csv(ROOT / "output" / "table2.csv", index=False, float_format="%.6f")
    print("wrote output/table1.csv and output/table2.csv")

if __name__ == "__main__":
    main()
