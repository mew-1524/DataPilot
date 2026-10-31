"""EDA statistics, chart data and plain-English insights (all computed from the data)."""
import numpy as np
import pandas as pd
from cleaning import kind, outlier_mask


def f(v):
    return None if v is None or pd.isna(v) else round(float(v), 4)


def eda(df):
    num = df.select_dtypes("number"); stats = {}
    for c in num:
        s = num[c].dropna()
        if s.empty: continue
        m = s.mode()
        stats[c] = dict(mean=f(s.mean()), median=f(s.median()), mode=f(m.iloc[0]) if len(m) else None,
                        std=f(s.std()), var=f(s.var()), min=f(s.min()), q1=f(s.quantile(.25)),
                        q3=f(s.quantile(.75)), p90=f(s.quantile(.9)), max=f(s.max()),
                        skew=f(s.skew()), kurt=f(s.kurt()))
    cats = {}
    for c in df.columns:
        if kind(df[c]) == "categorical" and df[c].notna().any():
            v = df[c].value_counts()
            cats[c] = dict(unique=int(len(v)), most=str(v.index[0]), least=str(v.index[-1]),
                           top=[[str(k), int(n), round(100 * n / len(df), 1)] for k, n in v.head(8).items()])
    corr = None
    if num.shape[1] > 1:
        cm = num.corr(); corr = dict(cols=list(cm.columns), matrix=[[f(x) for x in row] for row in cm.values])
    return dict(stats=stats, categories=cats, correlation=corr)


def chart(df, mode, x, y=None, agg="mean"):
    if x not in df.columns: raise ValueError("Choose a valid X column.")
    if mode == "hist":
        s = pd.to_numeric(df[x], errors="coerce").dropna()
        if kind(df[x]) != "numeric" or s.empty: raise ValueError("A histogram needs a numeric X column.")
        h, e = np.histogram(s, bins=min(12, max(5, int(np.sqrt(len(s))))))
        return dict(labels=[f"{e[i]:.3g} to {e[i + 1]:.3g}" for i in range(len(h))], values=h.tolist())
    if mode == "scatter":
        if y not in df.columns: raise ValueError("A scatter plot needs X and Y columns.")
        d = df[[x, y]].apply(pd.to_numeric, errors="coerce").dropna().head(1000)
        if d.empty: raise ValueError("Scatter plots need two numeric columns.")
        return dict(points=[dict(x=a, y=b) for a, b in d.values.tolist()])
    if y in df.columns and agg != "count":
        if kind(df[y]) != "numeric": raise ValueError("Y must be numeric for this aggregate.")
        g = df.groupby(x)[y].agg(agg)
    else:
        g = df[x].value_counts()
    g = g.dropna().sort_values(ascending=False).head(15)
    if kind(df[x]) in ("date", "numeric"): g = g.sort_index()
    return dict(labels=[str(i)[:40] for i in g.index], values=[f(v) for v in g.values])


def insights(df):
    out = []; n = len(df)
    num = [c for c in df.columns if kind(df[c]) == "numeric"]
    cat = [c for c in df.columns if kind(df[c]) == "categorical" and 1 < df[c].nunique() <= 30]
    for c in cat[:3]:
        v = df[c].value_counts()
        out.append(f"In '{c}', the most frequent value is '{v.index[0]}' ({v.iloc[0] / n:.1%} of rows).")
    for c in cat[:2]:
        for k in num[:3]:
            g = df.groupby(c)[k].mean().dropna()
            if len(g) > 1:
                out.append(f"Average '{k}' is highest for {c} = '{g.idxmax()}' ({g.max():.2f}) and lowest for '{g.idxmin()}' ({g.min():.2f}).")
    top = num[:15]
    for i, a in enumerate(top):
        for b in top[i + 1:]:
            r = df[a].corr(df[b])
            if pd.notna(r) and abs(r) >= .5:
                out.append(f"'{a}' and '{b}' are {'positively' if r > 0 else 'negatively'} correlated (r = {r:.2f}).")
    for c in num:
        k = int(outlier_mask(df[c]).sum())
        if k: out.append(f"'{c}' has {k} unusual values by the IQR rule. Review them in Data cleaning.")
    for c in df.columns:
        p = df[c].isna().mean()
        if p > .2: out.append(f"'{c}' is missing in {p:.0%} of rows, so results using it may be unreliable.")
    dates = [c for c in df.columns if kind(df[c]) == "date"]
    if dates and num:
        s = df.set_index(dates[0])[num[0]].dropna().sort_index()
        if len(s) >= 4:
            a, b = s.iloc[:len(s) // 2].mean(), s.iloc[len(s) // 2:].mean()
            if a:
                out.append(f"'{num[0]}' averages {a:.2f} in the first half of the period and {b:.2f} in the second half ({(b - a) / abs(a):+.1%}).")
    return out[:25] or ["No notable patterns were found."]
