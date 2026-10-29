"""Upload checks before anything reaches the model (plan §7 guardrails).

Every limit is checked on the bytes, not on what the client claims: the file
type comes from its signature (magic bytes), never the extension or the
Content-Type header. Image size is read from the header before any pixels are
decoded, so a decompression bomb is rejected without being expanded. PDFs are
only rasterised with pdfium, with no form environment, so scripts, embedded
files and links in the PDF are never run or followed.
"""

import io
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageOps

MAX_BYTES = 10 * 1024 * 1024
MAX_PDF_PAGES = 5
MAX_PIXELS = 40_000_000  # ~ A4 at 600 dpi (4960 x 7016 = 34.8 MP), with headroom
MIN_SIDE = 400  # px on the short side; below this text is unreadable
PDF_DPI = 150  # same resolution the synthetic invoices are rendered at
BLUR_MIN = 25.0  # Laplacian variance on a 1,024 px grey copy; calibrated on synth_v1
DARK_MAX = 40  # mean brightness (0-255) below which the photo is too dark

Image.MAX_IMAGE_PIXELS = MAX_PIXELS  # Pillow's own bomb guard as a second line


class IntakeError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass
class Quality:
    sharpness: float
    brightness: float
    width: int
    height: int

    @property
    def problems(self) -> list[str]:
        out = []
        if self.sharpness < BLUR_MIN:
            out.append("too_blurry")
        if self.brightness < DARK_MAX:
            out.append("too_dark")
        if min(self.width, self.height) < MIN_SIDE:
            out.append("too_small")
        return out


def sniff(data: bytes) -> str | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if data[:1024].lstrip().startswith(b"%PDF-"):
        return "pdf"
    return None


def _open_image(data: bytes) -> Image.Image:
    try:
        img = Image.open(io.BytesIO(data))  # reads the header only
    except Image.DecompressionBombError as e:
        raise IntakeError("too_many_pixels", str(e)) from e
    except Exception as e:
        raise IntakeError("corrupt_file", f"cannot read image: {e}") from e
    w, h = img.size
    if w * h > MAX_PIXELS:
        raise IntakeError("too_many_pixels", f"{w}x{h} is over the {MAX_PIXELS:,} pixel limit")
    try:
        img.load()
    except Exception as e:
        raise IntakeError("corrupt_file", f"cannot decode image: {e}") from e
    return ImageOps.exif_transpose(img).convert("RGB")


def _pdf_pages(data: bytes) -> list[Image.Image]:
    import pypdfium2 as pdfium

    try:
        pdf = pdfium.PdfDocument(data)  # no init_forms(): no JavaScript, no form actions
    except pdfium.PdfiumError as e:
        raise IntakeError("corrupt_file", f"cannot open PDF (encrypted or damaged): {e}") from e
    try:
        n = len(pdf)
        if n == 0:
            raise IntakeError("empty_pdf", "PDF has no pages")
        if n > MAX_PDF_PAGES:
            raise IntakeError("too_many_pages", f"{n} pages, the limit is {MAX_PDF_PAGES}")
        pages = []
        for page in pdf:
            w, h = page.get_size()  # points (1/72 inch)
            scale = PDF_DPI / 72
            if w * h * scale * scale > MAX_PIXELS:
                raise IntakeError("too_many_pixels", f"PDF page {w:.0f}x{h:.0f} pt is too large")
            pages.append(page.render(scale=scale).to_pil().convert("RGB"))
        return pages
    finally:
        pdf.close()


def quality(img: Image.Image) -> Quality:
    """Sharpness = variance of the Laplacian on a 1,024 px grey copy (low = blurry)."""
    g = img.convert("L")
    g.thumbnail((1024, 1024))
    a = np.asarray(g, dtype=np.float32)
    lap = (a[:-2, 1:-1] + a[2:, 1:-1] + a[1:-1, :-2] + a[1:-1, 2:] - 4 * a[1:-1, 1:-1])
    return Quality(sharpness=round(float(lap.var()), 1), brightness=round(float(a.mean()), 1),
                   width=img.width, height=img.height)


def load(data: bytes) -> tuple[str, list[Image.Image]]:
    """Check an upload and return (kind, pages). Raises IntakeError with a stable code."""
    if not data:
        raise IntakeError("empty_file", "file is empty")
    if len(data) > MAX_BYTES:
        raise IntakeError("too_large", f"{len(data):,} bytes, the limit is {MAX_BYTES:,}")
    kind = sniff(data)
    if kind is None:
        raise IntakeError("unsupported_type", "only JPG, PNG and PDF files are accepted")
    pages = _pdf_pages(data) if kind == "pdf" else [_open_image(data)]
    return kind, pages
