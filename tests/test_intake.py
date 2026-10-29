import io
import json
import struct
import zlib
from pathlib import Path

import pytest
from PIL import Image, ImageFilter

from invoice_lm import intake
from invoice_lm.intake import IntakeError

DATA = Path("data/synth_v1")


def _png(w=800, h=1100, color="white") -> bytes:
    b = io.BytesIO()
    Image.new("RGB", (w, h), color).save(b, "PNG")
    return b.getvalue()


def _pdf(pages: int = 1, js: bool = False) -> bytes:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument.new()
    for _ in range(pages):
        pdf.new_page(595, 842)
    b = io.BytesIO()
    pdf.save(b)
    data = b.getvalue()
    if js:  # an OpenAction script appended as an incremental update; must never run
        data += (b"\n9 0 obj << /Type /Action /S /JavaScript /JS (app.alert('x')) >> endobj\n")
    return data


def _code(data: bytes) -> str:
    with pytest.raises(IntakeError) as e:
        intake.load(data)
    return e.value.code


def test_accepts_png_jpeg_pdf():
    assert intake.load(_png())[0] == "png"
    b = io.BytesIO()
    Image.new("RGB", (800, 1100), "white").save(b, "JPEG")
    assert intake.load(b.getvalue())[0] == "jpeg"
    kind, pages = intake.load(_pdf(2))
    assert kind == "pdf" and len(pages) == 2 and pages[0].width == round(595 * 150 / 72)


def test_type_comes_from_signature_not_name():
    assert _code(b"MZ\x90\x00 this is an exe renamed to invoice.png") == "unsupported_type"
    assert _code(b"<svg xmlns='http://www.w3.org/2000/svg'></svg>") == "unsupported_type"
    assert _code(b"GIF89a" + b"\x00" * 100) == "unsupported_type"


def test_size_limits():
    assert _code(b"") == "empty_file"
    assert _code(b"\x89PNG\r\n\x1a\n" + b"\x00" * intake.MAX_BYTES) == "too_large"


def test_decompression_bomb_rejected_from_header():
    # A tiny PNG whose header claims 20,000 x 20,000 pixels: rejected before decoding.
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d))
    ihdr = struct.pack(">IIBBBBB", 20_000, 20_000, 8, 2, 0, 0, 0)
    bomb = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(b"\x00" * 64)) \
        + chunk(b"IEND", b"")
    assert len(bomb) < 200
    assert _code(bomb) == "too_many_pixels"


def test_corrupt_files():
    assert _code(_png()[:60]) == "corrupt_file"
    assert _code(b"%PDF-1.7\n garbage") == "corrupt_file"


def test_pdf_page_cap_and_script_ignored():
    assert _code(_pdf(intake.MAX_PDF_PAGES + 1)) == "too_many_pages"
    kind, pages = intake.load(_pdf(1, js=True))  # rendered as pixels only
    assert kind == "pdf" and len(pages) == 1


def test_quality_flags():
    assert intake.quality(Image.open(io.BytesIO(_png(800, 1100, (10, 10, 10))))).problems \
        == ["too_blurry", "too_dark"]
    assert "too_small" in intake.quality(Image.new("RGB", (300, 300), "white")).problems


@pytest.mark.skipif(not DATA.exists(), reason="dataset not built")
def test_dataset_images_pass_quality_and_blurred_ones_fail():
    rows = [json.loads(line) for line in (DATA / "manifest.jsonl").open()][:60]
    for r in rows:
        img = Image.open(DATA / r["image"])
        assert intake.quality(img).problems == [], r["id"]
    photo = next(r for r in rows if r["level"] == "photo")
    blurred = Image.open(DATA / photo["image"]).filter(ImageFilter.GaussianBlur(4))
    assert "too_blurry" in intake.quality(blurred).problems
