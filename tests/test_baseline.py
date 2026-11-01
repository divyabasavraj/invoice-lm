import json
import random

import httpx

from invoice_lm import baseline
from invoice_lm.generator.data import random_invoice


def _resp(status, body=None):
    req = httpx.Request("POST", "https://generativelanguage.googleapis.com/x")
    return httpx.Response(status, json=body or {}, request=req)


OK = {"candidates": [{"content": {"parts": [{"text": "{}"}]}}], "usageMetadata": {}}


def test_gemini_retries_rate_limit_then_succeeds(monkeypatch):
    calls = []
    replies = [_resp(429), _resp(503), _resp(200, OK)]
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.setattr(baseline.httpx, "post", lambda *a, **k: calls.append(1) or replies.pop(0))
    monkeypatch.setattr(baseline.time, "sleep", lambda s: None)
    out = baseline.call_gemini("gemini-2.5-flash", b"img", "image/png")
    assert out["text"] == "{}" and len(calls) == 3


def test_failed_call_is_not_cached(tmp_path, monkeypatch):
    ds = tmp_path / "ds"
    (ds / "labels").mkdir(parents=True)
    (ds / "images").mkdir()
    inv = random_invoice(random.Random(0))
    (ds / "labels" / "a.json").write_text(inv.model_dump_json())
    (ds / "images" / "a.png").write_bytes(b"x")
    (ds / "manifest.jsonl").write_text(json.dumps(
        {"id": "a", "split": "test", "image": "images/a.png", "label": "labels/a.json",
         "layout": "classic", "level": "clean"}) + "\n")

    def boom(*a, **k):
        raise httpx.ConnectError("down")
    monkeypatch.setattr(baseline, "predict", boom)
    s = baseline.run("gemini:x", ds, runs_dir=tmp_path / "runs")
    assert s["overall"]["n"] == 1
    # a transport/HTTP failure must be retried on the next run, not scored forever
    assert not (tmp_path / "runs" / "gemini_x" / "ds" / "a.json").exists()
