"""Make a clean render look like a scan or a phone photo.

Three difficulty levels, stored in the manifest so results can be broken down:
- clean: untouched
- scan:  slight skew, grey paper, speckle noise, lower JPEG quality
- photo: perspective tilt on a table background, uneven light, a shadow,
         blur, a fold line, smaller image, heavy JPEG
Only the image changes; the label is the same.
"""

import io
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

LEVELS = ("clean", "scan", "photo")
_TABLES = [(92, 64, 45), (140, 110, 80), (60, 60, 65), (180, 175, 165), (35, 45, 60)]


def _jpeg(img: Image.Image, quality: int) -> Image.Image:
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=quality)
    buf.seek(0)
    return Image.open(buf).convert("RGB")


def _noise(img: Image.Image, rng: random.Random, sigma: float) -> Image.Image:
    a = np.asarray(img, dtype=np.float32)
    n = np.random.default_rng(rng.getrandbits(32)).normal(0, sigma, a.shape[:2])[..., None]
    return Image.fromarray(np.clip(a + n, 0, 255).astype(np.uint8))


def _lighting(img: Image.Image, rng: random.Random) -> Image.Image:
    """Brightness falls off from a random light point; optional soft shadow."""
    w, h = img.size
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    cx, cy = rng.uniform(0, w), rng.uniform(0, h)
    dist = np.hypot(xs - cx, ys - cy) / np.hypot(w, h)
    gain = 1.08 - rng.uniform(0.25, 0.5) * dist
    if rng.random() < 0.6:  # shadow of a phone or hand across one side
        edge = rng.uniform(0.15, 0.45)
        along = xs / w if rng.random() < 0.5 else ys / h
        if rng.random() < 0.5:
            along = 1 - along
        gain *= np.where(along < edge, rng.uniform(0.55, 0.8), 1.0)
    tint = np.array([1.0, rng.uniform(0.95, 1.0), rng.uniform(0.85, 0.97)], dtype=np.float32)
    a = np.asarray(img, dtype=np.float32) * gain[..., None] * tint
    out = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    return out.filter(ImageFilter.GaussianBlur(0.6))


def _fold(img: Image.Image, rng: random.Random) -> Image.Image:
    d = ImageDraw.Draw(img, "RGBA")
    w, h = img.size
    y = int(h * rng.uniform(0.3, 0.7))
    d.line((0, y, w, y + rng.randint(-20, 20)), fill=(0, 0, 0, rng.randint(25, 60)), width=3)
    return img


def _perspective_coeffs(src, dst):
    """Coefficients for Image.transform(PERSPECTIVE) mapping dst -> src."""
    m = []
    for (x, y), (u, v) in zip(dst, src):
        m.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        m.append([0, 0, 0, x, y, 1, -v * x, -v * y])
    return np.linalg.solve(np.array(m, dtype=np.float64),
                           np.array(src, dtype=np.float64).reshape(8)).tolist()


def _photo_geometry(img: Image.Image, rng: random.Random) -> Image.Image:
    w, h = img.size
    pad = int(0.08 * w)
    cw, ch = w + 2 * pad, h + 2 * pad
    base = rng.choice(_TABLES)
    canvas = Image.new("RGB", (cw, ch), base)
    canvas = _noise(canvas, rng, 6)
    j = 0.045
    dst = [(pad + rng.uniform(-j, j) * w, pad + rng.uniform(-j, j) * h),
           (pad + w + rng.uniform(-j, j) * w, pad + rng.uniform(-j, j) * h),
           (pad + w + rng.uniform(-j, j) * w, pad + h + rng.uniform(-j, j) * h),
           (pad + rng.uniform(-j, j) * w, pad + h + rng.uniform(-j, j) * h)]
    src = [(0, 0), (w, 0), (w, h), (0, h)]
    coeffs = _perspective_coeffs(src, dst)
    warped = img.transform((cw, ch), Image.Transform.PERSPECTIVE, coeffs, Image.Resampling.BICUBIC)
    mask = Image.new("L", (w, h), 255).transform(
        (cw, ch), Image.Transform.PERSPECTIVE, coeffs, Image.Resampling.BILINEAR)
    canvas.paste(warped, (0, 0), mask)
    return canvas


def augment(img: Image.Image, rng: random.Random, level: str) -> Image.Image:
    if level == "clean":
        return img
    if level == "scan":
        paper = (rng.randint(232, 250),) * 3
        out = img.rotate(rng.uniform(-1.5, 1.5), Image.Resampling.BICUBIC, expand=False,
                         fillcolor=paper)
        a = np.asarray(out, dtype=np.float32)
        a = a * (np.array(paper) / 255.0)  # grey paper
        out = Image.fromarray(a.astype(np.uint8)).convert("L").convert("RGB")
        out = _noise(out, rng, rng.uniform(4, 9))
        return _jpeg(out, rng.randint(55, 80))
    if level == "photo":
        out = _fold(img.copy(), rng) if rng.random() < 0.4 else img
        out = _photo_geometry(out, rng)
        out = _lighting(out, rng)
        out = out.rotate(rng.uniform(-3, 3), Image.Resampling.BICUBIC, fillcolor=out.getpixel((2, 2)))
        if rng.random() < 0.5:
            out = out.filter(ImageFilter.GaussianBlur(rng.uniform(0.6, 1.4)))
        scale = rng.uniform(0.6, 0.85)
        out = out.resize((int(out.width * scale), int(out.height * scale)), Image.Resampling.LANCZOS)
        out = _noise(out, rng, rng.uniform(3, 7))
        return _jpeg(out, rng.randint(35, 70))
    raise ValueError(level)
