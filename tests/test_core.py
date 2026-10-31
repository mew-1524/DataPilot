import sys
from pathlib import Path
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from cleaning import OPS, quality, smart_types
from fastapi.testclient import TestClient
from main import app


def sample():
    return pd.DataFrame({"city": [" Pune", "pune", "Mumbai", "Mumbai", None], "sales": [10.0, 12.0, 11.0, 11.0, 500.0]})


def test_missing_does_not_mutate_input():
    df = sample(); new, n, _ = OPS["missing"](df, {"column": "city", "strategy": "custom", "value": "Unknown"})
    assert n == 1 and new["city"].isna().sum() == 0 and df["city"].isna().sum() == 1


def test_duplicates_and_text():
    _, n, _ = OPS["duplicates"](sample().iloc[[2, 3]], {}); assert n == 1
    new, _, _ = OPS["text"](sample(), {"column": "city", "case": "title"}); assert new["city"].dropna().nunique() == 2


def test_outliers_iqr():
    _, n, _ = OPS["outliers"](sample(), {"column": "sales", "method": "iqr", "action": "remove"}); assert n == 1


def test_quality_and_types():
    assert quality(sample())["score"] < 100
    assert smart_types(pd.DataFrame({"a": ["1", "2", "3"]}))["a"].dtype.kind in "if"


def test_api_flow():
    c = TestClient(app); csv = b"name,amount\n=cmd,5\nb,7\nb,7\n"
    sid = c.post("/api/upload", files={"file": ("t.csv", csv, "text/csv")}).json()["sid"]; h = {"X-SID": sid}
    assert c.get("/api/profile", headers=h).json()["profile"]["rows"] == 3
    assert c.post("/api/clean/duplicates", json={}, headers=h).json()["affected"] == 1
    assert c.post("/api/undo", headers=h).status_code == 200
    assert b"'=cmd" in c.get("/api/export/csv", headers=h).content
    assert c.get("/api/export/excel", headers=h).status_code == 200
    assert c.get("/api/profile", headers={"X-SID": "other"}).status_code == 404
    assert c.post("/api/upload", files={"file": ("x.exe", b"a", "text/plain")}).status_code == 400
