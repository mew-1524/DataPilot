"""Profiling, quality score and cleaning operations. Every operation returns
(new_dataframe, records_affected, column_label) and never changes its input."""
import numpy as np
import pandas as pd


def kind(s):
    if pd.api.types.is_bool_dtype(s): return "boolean"
    if pd.api.types.is_numeric_dtype(s): return "numeric"
    if pd.api.types.is_datetime64_any_dtype(s): return "date"
    return "categorical"


def textcols(df):
    return [c for c in df.columns if kind(df[c]) == "categorical"]


def smart_types(df):
    """Auto-detect numbers and dates stored as text."""
    df = df.copy()
    for c in textcols(df):
        s, filled = df[c], df[c].notna().sum()
        if not filled: continue
        n = pd.to_numeric(s, errors="coerce")
        if n.notna().sum() >= 0.95 * filled:
            df[c] = n
        elif any(h in c.lower() for h in ("date", "time", "day")):
            d = pd.to_datetime(s, errors="coerce")
            if d.notna().sum() >= 0.9 * filled: df[c] = d
    return df


def profile(df):
    cols = []
    for c in df.columns:
        s = df[c]; n = int(s.isna().sum()); u = int(s.nunique())
        cols.append(dict(name=c, dtype=str(s.dtype), kind=kind(s), missing=n,
                         missing_pct=round(100 * n / max(len(df), 1), 2), unique=u,
                         constant=u <= 1, id_like=bool(u == len(df) and len(df) > 1)))
    return dict(rows=len(df), cols=len(df.columns), duplicates=int(df.duplicated().sum()), columns=cols)


def quality(df):
    r, c = df.shape; cells = max(r * c, 1); txt = textcols(df)
    miss, dup = int(df.isna().sum().sum()), int(df.duplicated().sum())
    inf = int(np.isinf(df.select_dtypes("number")).sum().sum())
    blank = bad = 0
    for col in txt:
        v = df[col].dropna().astype(str); key = v.str.strip().str.lower()
        blank += int((key == "").sum())
        variants = v.groupby(key).nunique()
        bad += int(key.isin(variants[variants > 1].index).sum())
    tcells = max(r * len(txt), 1)
    m = dict(completeness=100 * (1 - miss / cells), uniqueness=100 * (1 - dup / max(r, 1)),
             validity=100 * (1 - (inf + blank) / cells), consistency=100 * (1 - bad / tcells))
    m = {k: round(max(v, 0), 1) for k, v in m.items()}
    rec = []
    if miss: rec.append(f"Fill or drop the {miss} missing cells (Data cleaning > Missing values).")
    if dup: rec.append(f"Remove {dup} duplicate rows.")
    if blank or inf: rec.append(f"Fix {blank + inf} invalid values (blank text or infinity).")
    if bad: rec.append(f"{bad} text values differ only by spaces or capitalization. Run Text cleaning.")
    const = [x for x in df.columns if df[x].nunique() <= 1]
    if const: rec.append("Constant columns carry no information: " + ", ".join(map(str, const)) + ".")
    return dict(score=round(sum(m.values()) / 4, 1), metrics=m, missing=miss,
                missing_pct=round(100 * miss / cells, 2), duplicates=dup,
                dup_pct=round(100 * dup / max(r, 1), 2), invalid=blank + inf, inconsistent=bad,
                recommendations=rec or ["No issues found. This dataset is analysis-ready."],
                columns=[dict(name=x, completeness=round(100 * (1 - df[x].isna().mean()), 1)) for x in df.columns])


def _col(df, p):
    c = p.get("column")
    if c not in df.columns: raise ValueError("Choose a valid column.")
    return c


def missing(df, p):
    c = _col(df, p); st = p.get("strategy"); s = df[c]; n = int(s.isna().sum())
    if st == "drop_rows": return df.dropna(subset=[c]), n, c
    if st == "drop_column": return df.drop(columns=[c]), n, c
    if st in ("mean", "median"):
        if kind(s) != "numeric": raise ValueError("Mean and median need a numeric column.")
        v = getattr(s, st)()
    elif st == "mode":
        m = s.mode(); v = m.iloc[0] if len(m) else None
    elif st == "custom":
        v = p.get("value")
        if v in (None, ""): raise ValueError("Enter a custom value.")
        if kind(s) == "numeric":
            try: v = float(v)
            except ValueError: raise ValueError("This column is numeric. Enter a number.")
    else: raise ValueError("Choose a strategy.")
    d = df.copy(); d[c] = s.fillna(v); return d, n, c


def duplicates(df, p):
    d = df.drop_duplicates(); return d, len(df) - len(d), "all columns"


def empty(df, p):
    d = df.dropna(how="all").dropna(axis=1, how="all")
    return d, (len(df) - len(d)) + (df.shape[1] - d.shape[1]), "all columns"


def text(df, p):
    c = p.get("column"); cols = textcols(df) if c == "*" else [_col(df, p)]
    case = p.get("case", "none"); d = df.copy(); n = 0
    for k in cols:
        if kind(d[k]) != "categorical": continue
        old = d[k].astype("string")
        new = old.str.strip().str.replace(r"\s+", " ", regex=True)
        if case in ("lower", "upper", "title"): new = getattr(new.str, case)()
        n += int((new.fillna("") != old.fillna("")).sum())
        d[k] = new.astype(object).where(new.notna(), np.nan)
    return d, n, c


def dtype(df, p):
    c = _col(df, p); t = p.get("type"); d = df.copy(); s = d[c]
    if t == "numeric": new = pd.to_numeric(s, errors="coerce")
    elif t == "integer": new = pd.to_numeric(s, errors="coerce").round().astype("Int64")
    elif t == "date": new = pd.to_datetime(s, errors="coerce")
    elif t == "text": new = s.astype("string").astype(object).where(s.notna(), np.nan)
    else: raise ValueError("Choose a target type.")
    d[c] = new; return d, int(new.notna().sum()), c


def outlier_mask(s, method="iqr"):
    if method == "zscore":
        sd = s.std(ddof=0)
        return ((s - s.mean()) / sd).abs() > 3 if sd else pd.Series(False, index=s.index)
    if method == "iforest":
        from sklearn.ensemble import IsolationForest
        x = s.dropna(); m = pd.Series(False, index=s.index)
        if len(x) > 10: m[x.index] = IsolationForest(random_state=0).fit_predict(x.to_frame()) == -1
        return m
    q1, q3 = s.quantile([.25, .75]); i = q3 - q1
    return (s < q1 - 1.5 * i) | (s > q3 + 1.5 * i)


def outliers(df, p):
    c = _col(df, p)
    if kind(df[c]) != "numeric": raise ValueError("Outlier detection needs a numeric column.")
    s = df[c]; m = outlier_mask(s, p.get("method", "iqr")); n = int(m.sum()); a = p.get("action", "remove")
    if a == "remove": return df[~m], n, c
    if a == "cap":
        q1, q3 = s.quantile([.25, .75]); i = q3 - q1; d = df.copy()
        d[c] = s.clip(q1 - 1.5 * i, q3 + 1.5 * i); return d, n, c
    raise ValueError("Choose an action.")


OPS = dict(missing=missing, duplicates=duplicates, empty=empty, text=text, dtype=dtype, outliers=outliers)
