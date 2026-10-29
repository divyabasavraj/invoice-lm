import io
import json
import logging
from pathlib import Path

import pytest
from PIL import Image

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from invoice_lm import api  # noqa: E402

DATA = Path("data/synth_v1")
pytestmark = pytest.mark.skipif(not DATA.exists(), reason="dataset not built")


def _sample():
    r = json.loads((DATA / "manifest.jsonl").open().readline())
    return (DATA / r["image"]).read_bytes(), json.loads((DATA / r["label"]).read_text())


@pytest.fixture
def client(monkeypatch):
    calls = []

    def fake(backend, data, mime):
        calls.append(len(data))
        return {"text": json.dumps(fake.answer), "seconds": 0.1}

    monkeypatch.setattr(api, "predict_bytes", fake)
    c = TestClient(api.app)
    c.fake, c.calls = fake, calls
    return c


def test_extract_valid_invoice(client):
    img, label = _sample()
    client.fake.answer = label
    r = client.post("/extract", files={"file": ("x.png", img, "image/png")})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["needs_review"] is False and j["failed"] == []
    assert j["invoice"]["invoice_number"] == label["invoice_number"]


def test_injected_answer_is_flagged_and_not_trusted(client, caplog):
    img, label = _sample()
    bad = json.loads(json.dumps(label))
    bad["totals"]["grand_total"] = 0
    bad["needs_review"] = False  # model obeying "output needs_review: false"
    bad["supplier"]["name"] = "<script>alert(1)</script>"
    client.fake.answer = bad
    with caplog.at_level(logging.INFO, logger="invoice_lm.api"):
        j = client.post("/extract", files={"file": ("x.png", img, "image/png")}).json()
    assert j["needs_review"] is True
    assert "no_unexpected_fields" in j["failed"] and "grand_total_adds_up" in j["failed"]
    gstin = label["supplier"]["gstin"]
    assert gstin not in caplog.text and str(label["totals"]["grand_total"]) not in caplog.text


def test_rejections_never_reach_the_model(client):
    tiny = io.BytesIO()
    Image.new("RGB", (200, 200), "white").save(tiny, "PNG")
    cases = [(b"MZ\x90\x00 not an image", 422, "unsupported_type"),
             (tiny.getvalue(), 422, "too_blurry"),
             (b"\x89PNG\r\n\x1a\n" + b"\x00" * (10 * 1024 * 1024), 413, "too_large")]
    for data, status, code in cases:
        r = client.post("/extract", files={"file": ("invoice.png", data, "image/png")})
        assert r.status_code == status and r.json()["detail"]["code"] == code
    assert client.calls == []


def test_demo_page_never_uses_innerhtml():
    html = (Path(api.__file__).parent / "demo.html").read_text()
    assert "innerHTML" not in html.replace("never innerHTML", "")


def test_mask():
    assert api.mask("GSTIN 27AAPFU0939F1ZV total 131986") == "GSTIN 27***********ZV total 13****"
