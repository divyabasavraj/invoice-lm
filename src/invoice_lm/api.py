"""HTTP service (milestone 8): upload an invoice, get validated JSON back.

    uv run --extra api uvicorn invoice_lm.api:app --port 8000

Pipeline: intake checks -> model -> validators. The model's answer is data only;
`needs_review` and `confidence` come from the validators, never from the model.
Logs carry check names and timings, never invoice contents: GSTINs and amounts
are personal/business data, and logs are kept longer than requests.
"""

import io
import logging
import os
import re
import threading
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse

from invoice_lm import intake
from invoice_lm.baseline import predict_bytes
from invoice_lm.validators import validate

BASE_MODEL = "mlx-community/Qwen3-VL-4B-Instruct-4bit"
ADAPTER = Path(__file__).resolve().parents[2] / "runs/train/qwen3vl4b_lora_r16/adapters"
# Best untrained model in pass 1; used when the adapter isn't on disk (e.g. a fresh clone).
FALLBACK_BACKEND = "ollama:qwen3-vl:4b-instruct"


def default_backend(adapter: Path = ADAPTER) -> str:
    """The LoRA fine-tune if its weights are present, else the best untrained model."""
    if (adapter / "adapters.safetensors").exists():
        return f"mlx:{BASE_MODEL}+{adapter}"
    return FALLBACK_BACKEND


def backend_label(backend: str) -> str:
    """Backend name for responses: the adapter's run name, never a local path."""
    model, plus, adapter = backend.partition("+")
    return f"{model}+lora:{Path(adapter).parent.name}" if plus else backend


BACKEND = os.environ.get("INVOICE_LM_BACKEND") or default_backend()
HARD_PROBLEMS = {"too_blurry", "too_small", "too_dark"}

log = logging.getLogger("invoice_lm.api")
app = FastAPI(title="InvoiceLM", version="0.1.0")
_model_lock = threading.Lock()  # one model call at a time: 16 GB machine, one heavy job


def mask(text: str) -> str:
    """Hide GSTINs and long digit runs in anything that might reach a log."""
    text = re.sub(r"\b(\d{2})[A-Z0-9]{11}([A-Z0-9]{2})\b", r"\1***********\2", text)
    return re.sub(r"\d{5,}", lambda m: m.group()[:2] + "*" * (len(m.group()) - 2), text)


@app.get("/health")
def health() -> dict:
    return {"ok": True, "backend": backend_label(BACKEND)}


@app.post("/extract")
async def extract(file: UploadFile = File(...)) -> dict:
    rid = uuid.uuid4().hex[:8]
    data = await file.read(intake.MAX_BYTES + 1)  # never read more than the limit + 1 byte
    try:
        kind, pages = intake.load(data)
    except intake.IntakeError as e:
        log.info("%s rejected %s", rid, e.code)
        raise HTTPException(status_code=413 if e.code == "too_large" else 422,
                            detail={"code": e.code, "message": str(e)}) from None
    q = intake.quality(pages[0])
    hard = [p for p in q.problems if p in HARD_PROBLEMS]
    if hard:
        log.info("%s rejected %s", rid, ",".join(hard))
        raise HTTPException(status_code=422, detail={
            "code": hard[0], "message": "image quality too low to read reliably: "
            + ", ".join(hard) + ". Please retake the photo.", "quality": q.__dict__})

    buf = io.BytesIO()
    pages[0].save(buf, "PNG")
    t0 = time.time()
    with _model_lock:
        try:
            out = predict_bytes(BACKEND, buf.getvalue(), "image/png")
        except Exception as e:
            log.warning("%s model error %s", rid, type(e).__name__)
            raise HTTPException(status_code=503, detail={"code": "model_unavailable",
                                                         "message": type(e).__name__}) from None
    rep = validate(out["text"])
    warnings = []
    if len(pages) > 1:
        warnings.append(f"only page 1 of {len(pages)} was read")
    if rep.invoice is None:
        warnings.append("no invoice could be read from this file (not an invoice, or unreadable)")
    log.info("%s %s %dB pages=%d review=%s conf=%.2f failed=%s %.1fs", rid, kind, len(data),
             len(pages), rep.needs_review, rep.confidence, ",".join(rep.failed), time.time() - t0)
    return {
        "request_id": rid,
        "invoice": rep.invoice.model_dump(mode="json") if rep.invoice else None,
        **rep.to_dict(),
        "warnings": warnings,
        "quality": q.__dict__,
        "model": {"backend": backend_label(BACKEND), "seconds": out.get("seconds")},
    }


@app.get("/", response_class=HTMLResponse)
def demo() -> str:
    return (Path(__file__).parent / "demo.html").read_text()
