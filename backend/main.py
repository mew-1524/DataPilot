"""DataPilot API.  Run from this folder:  uvicorn main:app --reload"""
import io, json, time, uuid, warnings
from datetime import datetime
from pathlib import Path

import pandas as pd
from fastapi import Body, Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from analytics import chart, eda, insights
from chat import answer as chat_answer
from cleaning import OPS, kind, profile, quality, smart_types, textcols

warnings.filterwarnings("ignore")
MAX_BYTES, TTL = 20 * 1024 * 1024, 3600          # 20 MB uploads, sessions expire after 1 hour
SESSIONS = {}                                    # sid -> {orig, df, hist, log, name, size, t}
app = FastAPI(title="DataPilot", docs_url="/api/docs")


@app.exception_handler(ValueError)
async def value_error(_, e):
    return JSONResponse({"detail": str(e)}, status_code=400)


def cur(x_sid: str = Header(None)):
    now = time.time()
    for k in [k for k, v in SESSIONS.items() if now - v["t"] > TTL]: del SESSIONS[k]   # expire old data
    s = SESSIONS.get(x_sid or "")
    if not s: raise HTTPException(404, "No dataset in this session. Upload a CSV first.")
    s["t"] = now
    return s


def read_csv(raw):
    for enc in ("utf-8-sig", "latin-1"):
        try:
            df = pd.read_csv(io.BytesIO(raw), encoding=enc, skipinitialspace=True, on_bad_lines="skip")
        except UnicodeDecodeError: continue
        except Exception as e: raise ValueError("This file could not be read as a CSV.") from e
        if not len(df.columns): raise ValueError("The CSV has no columns.")
        df.columns = [str(c).strip() for c in df.columns]
        return df


def stamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    if not (file.filename or "").lower().endswith(".csv"): raise ValueError("Only .csv files are accepted.")
    raw = await file.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES: raise ValueError("The file is larger than 20 MB.")
    if not raw.strip(): raise ValueError("The file is empty.")
    df = smart_types(read_csv(raw)); sid = uuid.uuid4().hex
    SESSIONS[sid] = dict(orig=df, df=df.copy(), hist=[], log=[], t=time.time(),
                         name=Path(file.filename).name, size=len(raw))
    return dict(sid=sid)


@app.get("/api/profile")
def prof(s=Depends(cur)):
    return dict(name=s["name"], size=s["size"], profile=profile(s["df"]), steps=len(s["log"]),
                original=dict(rows=len(s["orig"]), cols=len(s["orig"].columns)))


def filtered(d, q="", sort="", desc=False):
    if q: d = d[d.astype(str).apply(lambda c: c.str.contains(q, case=False, regex=False)).any(axis=1)]
    if sort in d.columns: d = d.sort_values(sort, ascending=not desc, kind="stable")
    return d


@app.get("/api/rows")
def rows(page: int = 1, size: int = 25, q: str = "", sort: str = "", desc: bool = False, s=Depends(cur)):
    size = min(max(size, 1), 200); d = filtered(s["df"], q, sort, desc); a = (max(page, 1) - 1) * size
    return dict(columns=list(d.columns), total=len(d),
                rows=json.loads(d.iloc[a:a + size].to_json(orient="records", date_format="iso")))


@app.post("/api/clean/{op}")
def clean(op: str, p: dict = Body(default={}), s=Depends(cur)):
    if op not in OPS: raise HTTPException(404, "Unknown cleaning operation.")
    new, n, col = OPS[op](s["df"], p)
    if p.get("preview"): return dict(preview=True, affected=n)
    s["hist"] = (s["hist"] + [s["df"]])[-20:]; s["df"] = new
    s["log"].append(dict(operation=op, column=col, affected=n, time=stamp(), status="applied"))
    return dict(affected=n)


@app.post("/api/undo")
def undo(s=Depends(cur)):
    if not s["hist"]: raise ValueError("Nothing to undo.")
    s["df"] = s["hist"].pop()
    s["log"].append(dict(operation="undo", column="-", affected=0, time=stamp(), status="applied"))
    return dict(ok=True)


@app.post("/api/reset")
def reset(s=Depends(cur)):
    s["df"], s["hist"] = s["orig"].copy(), []
    s["log"].append(dict(operation="reset", column="-", affected=0, time=stamp(), status="applied"))
    return dict(ok=True)


@app.get("/api/log")
def log(s=Depends(cur)): return s["log"]


@app.get("/api/quality")
def qual(s=Depends(cur)): return quality(s["df"])


@app.get("/api/eda")
def eda_ep(s=Depends(cur)): return eda(s["df"])


@app.get("/api/chart")
def chart_ep(mode: str = "group", x: str = "", y: str = "", agg: str = "mean", s=Depends(cur)):
    if agg not in ("mean", "sum", "count", "median", "max", "min"): raise ValueError("Unknown aggregate.")
    return chart(s["df"], mode, x, y or None, agg)


@app.get("/api/insights")
def ins(s=Depends(cur)): return insights(s["df"])


@app.post("/api/chat")
async def chat_ep(p: dict = Body(default={}), s=Depends(cur)):
    message = p.get("message")
    if not isinstance(message, str) or not message.strip(): raise ValueError("Type a question first.")
    history = p.get("history", [])
    if not isinstance(history, list): history = []
    try:
        return {"answer": await chat_answer(s["df"], message.strip(), history)}
    except RuntimeError as e:
        raise HTTPException(503, str(e)) from e


def safe(d):
    """Prefix risky text so Excel never runs it as a formula (CSV injection)."""
    d = d.copy()
    for c in textcols(d):
        d[c] = d[c].map(lambda v: "'" + v if isinstance(v, str) and v and v[0] in "=+-@\t\r" else v)
    return d


def send(buf, name, mime):
    buf.seek(0)
    return StreamingResponse(buf, media_type=mime, headers={"Content-Disposition": f'attachment; filename="{name}"'})


@app.get("/api/export/csv")
def ex_csv(q: str = "", sort: str = "", desc: bool = False, s=Depends(cur)):
    data = safe(filtered(s["df"], q, sort, desc)).to_csv(index=False).encode("utf-8-sig")
    return send(io.BytesIO(data), "cleaned_data.csv", "text/csv")


LOGCOLS = ["operation", "column", "affected", "time", "status"]


@app.get("/api/export/excel")
def ex_xlsx(s=Depends(cur)):
    b = io.BytesIO()
    with pd.ExcelWriter(b, engine="openpyxl") as w:
        safe(s["df"]).to_excel(w, sheet_name="Cleaned data", index=False)
        pd.DataFrame(s["log"], columns=LOGCOLS).to_excel(w, sheet_name="Cleaning log", index=False)
    return send(b, "cleaned_data.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.get("/api/export/log")
def ex_log(s=Depends(cur)):
    d = pd.DataFrame(s["log"], columns=LOGCOLS)
    return send(io.BytesIO(d.to_csv(index=False).encode()), "cleaning_log.csv", "text/csv")


app.mount("/", StaticFiles(directory=Path(__file__).resolve().parent.parent / "frontend", html=True))
