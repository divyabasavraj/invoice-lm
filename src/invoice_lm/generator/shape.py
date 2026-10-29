"""Correct Devanagari / Kannada text without libraqm.

Pillow only shapes complex scripts through libraqm + libfribidi, which aren't
on this machine (no Homebrew), so it draws conjuncts and vowel signs in the
wrong places. Here HarfBuzz (uharfbuzz wheel) does the shaping and FreeType
(freetype-py wheel) rasterises each glyph. `ShapedDraw` wraps an ImageDraw:
Latin runs still go through Pillow, Indic runs through HarfBuzz, on the same
baseline, so the renderer only changes the line that creates its `draw`.
"""

import re
from functools import lru_cache
from pathlib import Path

import freetype
import numpy as np
import uharfbuzz as hb
from PIL import Image, ImageColor, ImageDraw

SCRIPT_FONTS = {  # script -> (font file, face index)
    "deva": ("/System/Library/Fonts/Supplemental/Devanagari Sangam MN.ttc", 0),
    "knda": ("/System/Library/Fonts/NotoSansKannada.ttc", 0),
}
_RUN = re.compile(r"([ऀ-ॿ᳐-᳿꣠-ꣿ]+(?:[ ऀ-ॿ]*[ऀ-ॿ])?"
                  r"|[ಀ-೿]+(?:[ ಀ-೿]*[ಀ-೿])?)")


def script_of(run: str) -> str | None:
    if re.search(r"[ऀ-ॿ]", run):
        return "deva"
    if re.search(r"[ಀ-೿]", run):
        return "knda"
    return None


def has_indic(text: str) -> bool:
    return script_of(text) is not None


@lru_cache(maxsize=None)
def _hb_font(path: str, index: int) -> hb.Font:
    blob = hb.Blob.from_file_path(path)
    return hb.Font(hb.Face(blob, index))


@lru_cache(maxsize=None)
def _ft_face(path: str, index: int) -> freetype.Face:
    return freetype.Face(path, index=index)


def shape(text: str, script: str, size: int) -> list[tuple[int, float, float, float]]:
    """(glyph id, x offset, y offset, x advance) in pixels."""
    path, index = SCRIPT_FONTS[script]
    font = _hb_font(path, index)
    font.scale = (size * 64, size * 64)
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(font, buf, {"kern": True, "liga": True})
    return [(i.codepoint, p.x_offset / 64, p.y_offset / 64, p.x_advance / 64)
            for i, p in zip(buf.glyph_infos, buf.glyph_positions)]


def runs(text: str) -> list[tuple[str, str | None]]:
    out, pos = [], 0
    for m in _RUN.finditer(text):
        if m.start() > pos:
            out.append((text[pos:m.start()], None))
        out.append((m.group(), script_of(m.group())))
        pos = m.end()
    if pos < len(text):
        out.append((text[pos:], None))
    return out


class ShapedDraw:
    """Drop-in for the parts of ImageDraw the renderer uses (text, textlength, rest passed on)."""

    def __init__(self, img: Image.Image):
        self._img = img
        self._d = ImageDraw.Draw(img)

    def __getattr__(self, name):
        return getattr(self._d, name)

    def _indic_width(self, run: str, script: str, size: int) -> float:
        return sum(g[3] for g in shape(run, script, size))

    def textlength(self, text: str, font=None, **kw) -> float:
        if not has_indic(text):
            return self._d.textlength(text, font=font, **kw)
        return sum(self._d.textlength(r, font=font) if s is None
                   else self._indic_width(r, s, font.size) for r, s in runs(text))

    def text(self, xy, text, fill=None, font=None, **kw):
        if not has_indic(text):
            return self._d.text(xy, text, fill=fill, font=font, **kw)
        x, y = xy
        baseline = y + font.getmetrics()[0]
        rgb = ImageColor.getrgb(fill) if isinstance(fill, str) else fill
        for r, s in runs(text):
            if s is None:
                self._d.text((x, y), r, fill=fill, font=font)
                x += self._d.textlength(r, font=font)
                continue
            face = _ft_face(*SCRIPT_FONTS[s])
            face.set_pixel_sizes(0, font.size)
            pen = x
            for gid, dx, dy, adv in shape(r, s, font.size):
                face.load_glyph(gid, freetype.FT_LOAD_RENDER | freetype.FT_LOAD_TARGET_NORMAL)
                g = face.glyph
                bm = g.bitmap
                if bm.width and bm.rows:
                    a = np.array(bm.buffer, dtype=np.uint8).reshape(bm.rows, bm.pitch)[:, :bm.width]
                    mask = Image.fromarray(a, "L")
                    gx = round(pen + dx + g.bitmap_left)
                    gy = round(baseline - dy - g.bitmap_top)
                    self._img.paste(Image.new(self._img.mode, mask.size, rgb[:3]), (gx, gy), mask)
                pen += adv
            x = pen


def draw_for(img: Image.Image, *texts: str):
    """ShapedDraw if any of the texts needs Indic shaping, else a plain ImageDraw."""
    return ShapedDraw(img) if any(has_indic(t or "") for t in texts) else ImageDraw.Draw(img)
