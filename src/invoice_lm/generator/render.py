"""Draw a GSTInvoice as a clean A4-proportioned PNG with Pillow.

Layouts: "classic" (bordered table), "minimal" (rules only), "handwritten"
(printed bill-book form filled in by hand, blue ink) and "thermal" (narrow
shop receipt, see render_thermal). Phone-photo effects are applied afterwards
by augment.py.
"""

import random
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from invoice_lm.generator.shape import draw_for
from invoice_lm.schema import GSTInvoice, SupplyType

W, H = 1240, 1754  # A4 at 150 dpi
MARGIN = 70

_FONT_DIRS = [Path("/System/Library/Fonts"), Path("/System/Library/Fonts/Supplemental")]
FONT_FAMILIES = {
    "helvetica": ("Helvetica.ttc", 0, 1),  # file, regular index, bold index
    "arial": ("Arial.ttf", "Arial Bold.ttf"),
    "times": ("Times.ttc", 0, 1),
    "courier": ("Courier New.ttf", "Courier New Bold.ttf"),
}
HAND_FAMILIES = {
    "bradley": ("Bradley Hand Bold.ttf", "Bradley Hand Bold.ttf"),
    "chalkboard": ("Chalkboard.ttc", 0, 1),
    "comic": ("Comic Sans MS.ttf", "Comic Sans MS Bold.ttf"),
}
LAYOUTS = ("classic", "minimal", "handwritten", "thermal")
LAYOUT_WEIGHTS = (0.35, 0.3, 0.15, 0.2)


def printed_label(inv: GSTInvoice, layout: str) -> GSTInvoice:
    """The label as it appears on this layout: fields the image doesn't show become null.

    The model must copy what is printed, not compute it, so the label can't
    contain values the image never shows.
    """
    out = inv.model_copy(deep=True)
    for it in out.line_items:
        it.total = None  # no layout prints a per-line total
        if layout == "thermal":
            it.cgst_amount = it.sgst_amount = it.igst_amount = None
    if layout == "thermal":
        out.supplier.state = out.supplier.state_code = None
        out.buyer.address = out.buyer.state = out.buyer.state_code = None
    return out


def _load(spec, size: int, bold: bool) -> ImageFont.FreeTypeFont:
    if isinstance(spec[1], int):
        name, index = spec[0], spec[2] if bold else spec[1]
    else:
        name, index = spec[1] if bold else spec[0], 0
    for d in _FONT_DIRS:
        if (d / name).exists():
            return ImageFont.truetype(str(d / name), size, index=index)
    raise FileNotFoundError(name)


@dataclass
class Fonts:
    small: ImageFont.FreeTypeFont
    small_bold: ImageFont.FreeTypeFont
    body: ImageFont.FreeTypeFont
    bold: ImageFont.FreeTypeFont
    title: ImageFont.FreeTypeFont

    @classmethod
    def of(cls, family: str, scale: float = 1.0) -> "Fonts":
        spec = FONT_FAMILIES.get(family) or HAND_FAMILIES[family]
        return cls(_load(spec, int(18 * scale), False), _load(spec, int(18 * scale), True),
                   _load(spec, int(21 * scale), False),
                   _load(spec, int(21 * scale), True), _load(spec, int(34 * scale), True))


def inr(x: float) -> str:
    """Indian digit grouping: 1234567.5 -> 12,34,567.50"""
    neg, x = x < 0, abs(x)
    whole, frac = f"{x:.2f}".split(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join(groups + [tail])
    return f"{'-' if neg else ''}{whole}.{frac}"


_ONES = ("Zero One Two Three Four Five Six Seven Eight Nine Ten Eleven Twelve Thirteen "
         "Fourteen Fifteen Sixteen Seventeen Eighteen Nineteen").split()
_TENS = "_ _ Twenty Thirty Forty Fifty Sixty Seventy Eighty Ninety".split()


def _words_below_1000(n: int) -> str:
    parts = []
    if n >= 100:
        parts += [_ONES[n // 100], "Hundred"]
        n %= 100
    if n >= 20:
        parts.append(_TENS[n // 10])
        n %= 10
    if n:
        parts.append(_ONES[n])
    return " ".join(parts)


def amount_in_words(rupees: int) -> str:
    """Indian system: crore, lakh, thousand."""
    if rupees == 0:
        return "Rupees Zero Only"
    parts = []
    for div, name in ((10**7, "Crore"), (10**5, "Lakh"), (1000, "Thousand")):
        if rupees >= div:
            parts += [_words_below_1000(rupees // div), name]
            rupees %= div
    if rupees:
        parts.append(_words_below_1000(rupees))
    return "Rupees " + " ".join(parts) + " Only"


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, width: int) -> list[str]:
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if draw.textlength(trial, font=font) <= width:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    return lines + [cur] if cur else lines


def render(inv: GSTInvoice, rng: random.Random, layout: str | None = None,
           family: str | None = None) -> tuple[Image.Image, dict]:
    """Returns the image and the render settings (stored next to the label)."""
    layout = layout or rng.choices(LAYOUTS, LAYOUT_WEIGHTS)[0]
    if layout == "thermal":
        return render_thermal(inv, rng, family)
    family = family or rng.choice(list(FONT_FAMILIES))
    f = Fonts.of(family)
    ink = (20, 20, 20)
    accent = rng.choice([(20, 20, 20), (25, 55, 120), (120, 30, 30), (20, 90, 60)])
    settings = {"layout": layout, "font": family}
    if layout == "handwritten":
        # Values written by hand in ballpoint; the printed form stays in `f`.
        hand = rng.choice(list(HAND_FAMILIES))
        v, vink = Fonts.of(hand, rng.uniform(1.0, 1.12)), rng.choice([(25, 40, 140), (20, 20, 60)])
        settings["hand_font"] = hand
    else:
        v, vink = f, ink
    img = Image.new("RGB", (W, H), (255, 255, 255))
    d = draw_for(img, inv.model_dump_json())
    boxed = layout in ("classic", "handwritten")
    jitter = 2 if layout == "handwritten" else 0

    def vt(xy, text, font, fill=vink):
        """Draw a value (handwritten layouts wobble a little)."""
        d.text((xy[0] + rng.randint(-jitter, jitter), xy[1] + rng.randint(-jitter, jitter)),
               text, font=font, fill=fill)

    x0, x1 = MARGIN, W - MARGIN
    y = MARGIN

    # Header: supplier (pre-printed even on hand-filled bill books)
    s = inv.supplier
    addr = _wrap(d, s.address or "", f.body, 640)
    band = layout != "handwritten" and rng.random() < 0.3
    head_ink, title_ink = (ink, accent)
    if band:
        d.rectangle((0, 0, W, MARGIN + 46 + 26 * len(addr) + 52 + 20), fill=accent)
        head_ink = title_ink = (255, 255, 255)
    settings["header"] = "band" if band else "plain"
    d.text((x0, y), s.name.upper(), font=f.title, fill=title_ink)
    y += 46
    for line in addr:
        d.text((x0, y), line, font=f.body, fill=head_ink)
        y += 26
    d.text((x0, y), f"GSTIN: {s.gstin}", font=f.bold, fill=head_ink)
    y += 26
    d.text((x0, y), f"State: {s.state}, Code: {s.state_code}", font=f.body, fill=head_ink)
    title = "TAX INVOICE"
    d.text((x1 - d.textlength(title, font=f.title), MARGIN), title, font=f.title, fill=title_ink)
    y += 44
    if not band:
        d.line((x0, y, x1, y), fill=accent, width=3)
    y += 18

    # Invoice meta (right) and buyer (left)
    meta = [("Invoice No.", inv.invoice_number),
            ("Invoice Date", inv.invoice_date.strftime(rng.choice(["%d-%m-%Y", "%d/%m/%Y", "%d %b %Y"]))),
            ("Place of Supply", inv.place_of_supply or ""),
            ("Reverse Charge", "Yes" if inv.reverse_charge else "No")]
    my = y
    label_w = max(d.textlength(f"{k}:", font=f.bold) for k, _ in meta)
    value_w = max(d.textlength(val, font=v.body) for _, val in meta)
    mx = min(760, x1 - label_w - value_w - 16)
    for k, val in meta:
        d.text((mx, my), f"{k}:", font=f.bold, fill=ink)
        vt((mx + label_w + 16, my), val, v.body)
        my += 30
    b = inv.buyer
    d.text((x0, y), "Bill To:", font=f.bold, fill=accent)
    by = y + 28
    vt((x0, by), b.name, v.bold)
    by += 28
    for line in _wrap(d, b.address or "", v.body, 620):
        vt((x0, by), line, v.body)
        by += 28
    vt((x0, by), f"GSTIN: {b.gstin or 'Unregistered'}", v.body)
    by += 28
    vt((x0, by), f"State: {b.state}, Code: {b.state_code}", v.body)
    y = max(by, my) + 40

    # Line items
    intra = inv.supply_type == SupplyType.INTRA_STATE
    cols = [("#", 40), ("Description", 270), ("HSN/SAC", 100), ("Qty", 70), ("Unit", 80),
            ("Rate", 120), ("Taxable", 140), ("GST%", 70)]
    cols += [("CGST", 110), ("SGST", 110)] if intra else [("IGST", 200)]
    scale = (x1 - x0) / sum(w for _, w in cols)
    xs = [x0]
    for _, w in cols:
        xs.append(xs[-1] + int(w * scale))
    xs[-1] = x1
    row_h = 36
    if boxed:
        d.rectangle((x0, y, x1, y + row_h), fill=(235, 235, 235))
    for i, ((name, _), cx) in enumerate(zip(cols, xs)):
        if i == 3 or i >= 5:  # numeric columns: right-aligned header
            cx = xs[i + 1] - 14 - d.textlength(name, font=f.small_bold)
        d.text((cx + 6, y + 9), name, font=f.small_bold, fill=ink)
    top = y
    y += row_h
    if not boxed:
        d.line((x0, y, x1, y), fill=ink, width=2)
    for n, it in enumerate(inv.line_items, 1):
        desc_lines = _wrap(d, it.description, v.small, xs[2] - xs[1] - 10)
        cells = [str(n), None, it.hsn_sac or "", f"{it.quantity:g}" if it.quantity else "",
                 it.unit or "", inr(it.rate) if it.rate else "", inr(it.taxable_value),
                 f"{it.gst_rate:g}"]
        cells += ([inr(it.cgst_amount or 0), inr(it.sgst_amount or 0)] if intra
                  else [inr(it.igst_amount or 0)])
        h = max(row_h, 10 + 24 * len(desc_lines))
        for i, (cell, cx) in enumerate(zip(cells, xs)):
            if cell is None:
                for k, line in enumerate(desc_lines):
                    vt((cx + 6, y + 8 + 24 * k), line, v.small)
            elif i == 3 or i >= 5:  # numbers right-aligned
                vt((xs[i + 1] - 8 - d.textlength(cell, font=v.small), y + 8), cell, v.small)
            else:
                vt((cx + 6, y + 8), cell, v.small)
        y += h
        if boxed:
            d.line((x0, y, x1, y), fill=(180, 180, 180), width=1)
    if boxed:
        d.rectangle((x0, top, x1, y), outline=ink, width=2)
        for cx in xs[1:-1]:
            d.line((cx, top, cx, y), fill=(150, 150, 150), width=1)
    else:
        d.line((x0, y, x1, y), fill=ink, width=2)
    y += 24

    # Totals
    t = inv.totals
    rows = [("Taxable Value", t.taxable_value)]
    rows += [("CGST", t.cgst), ("SGST", t.sgst)] if intra else [("IGST", t.igst)]
    rows += [("Round Off", t.round_off), ("Grand Total", t.grand_total)]
    widest = max(d.textlength(k, font=f.bold) + d.textlength(f"Rs. {inr(amt)}", font=v.bold)
                 for k, amt in rows)
    tx = min(800, x1 - 8 - widest - 30)
    for k, amt in rows:
        font, vfont = (f.bold, v.bold) if k == "Grand Total" else (f.body, v.body)
        d.text((tx, y), k, font=font, fill=ink)
        val = f"Rs. {inr(amt)}"
        vt((x1 - 8 - d.textlength(val, font=vfont), y), val, vfont)
        y += 32
    y += 10
    d.text((x0, y), "Amount in words:", font=f.body, fill=ink)
    lead = d.textlength("Amount in words: ", font=f.body)
    for k, line in enumerate(_wrap(d, amount_in_words(int(t.grand_total)), v.body, x1 - x0 - lead)):
        vt((x0 + lead, y), line, v.body)
        y += 28

    # Footer
    fy = H - MARGIN - 140
    if y > fy - 10:
        raise ValueError("invoice content overflows the page")
    d.text((x0, fy), "Declaration: We declare that this invoice shows the actual price of the",
           font=f.small, fill=ink)
    d.text((x0, fy + 24), "goods/services described and that all particulars are true and correct.",
           font=f.small, fill=ink)
    sig = f"For {s.name}"
    d.text((x1 - d.textlength(sig, font=f.bold), fy), sig, font=f.bold, fill=ink)
    auth = "Authorised Signatory"
    d.text((x1 - d.textlength(auth, font=f.body), fy + 100), auth, font=f.body, fill=ink)

    return img, settings


def render_thermal(inv: GSTInvoice, rng: random.Random,
                   family: str | None = None) -> tuple[Image.Image, dict]:
    """80 mm shop receipt: one narrow monospace column, items stacked."""
    family = family or "courier"
    spec = FONT_FAMILIES.get(family, FONT_FAMILIES["courier"])
    font, bold = _load(spec, 20, False), _load(spec, 20, True)
    big = _load(spec, 26, True)
    rw, pad, lh = 600, 28, 26
    img = Image.new("RGB", (rw, 2600), (255, 255, 255))
    d = draw_for(img, inv.model_dump_json())
    ink = (30, 30, 30)
    y = pad
    inner = rw - 2 * pad

    def center(text, f=font):
        nonlocal y
        for line in _wrap(d, text, f, inner):
            d.text(((rw - d.textlength(line, font=f)) / 2, y), line, font=f, fill=ink)
            y += lh + (6 if f is big else 0)

    def lr(left, right, f=font):
        nonlocal y
        d.text((pad, y), left, font=f, fill=ink)
        d.text((rw - pad - d.textlength(right, font=f), y), right, font=f, fill=ink)
        y += lh

    def rule(ch="-"):
        nonlocal y
        n = int(inner // d.textlength(ch, font=font))
        d.text((pad, y), ch * n, font=font, fill=ink)
        y += lh

    s, b, t = inv.supplier, inv.buyer, inv.totals
    intra = inv.supply_type == SupplyType.INTRA_STATE
    money = inr if rng.random() < 0.5 else (lambda x: f"{x:.2f}")
    center(s.name.upper(), big)
    center(s.address or "")
    center(f"GSTIN: {s.gstin}")
    center("TAX INVOICE", bold)
    rule("=")
    lr(f"Bill: {inv.invoice_number}", inv.invoice_date.strftime(rng.choice(["%d/%m/%Y", "%d-%m-%y"])))
    d.text((pad, y), f"To: {b.name}", font=font, fill=ink)
    y += lh
    if b.gstin:
        d.text((pad, y), f"GSTIN: {b.gstin}", font=font, fill=ink)
        y += lh
    d.text((pad, y), f"POS: {inv.place_of_supply}", font=font, fill=ink)
    y += lh
    rule()
    lr("Item", "Amount", bold)
    rule()
    for it in inv.line_items:
        for line in _wrap(d, it.description, font, inner):
            d.text((pad, y), line, font=font, fill=ink)
            y += lh
        lr(f" {it.quantity:g} {it.unit} x {money(it.rate)}", money(it.taxable_value))
        d.text((pad, y), f" HSN {it.hsn_sac}  GST {it.gst_rate:g}%", font=font, fill=ink)
        y += lh
    rule()
    lr("Taxable Value", money(t.taxable_value))
    if intra:
        lr("CGST", money(t.cgst))
        lr("SGST", money(t.sgst))
    else:
        lr("IGST", money(t.igst))
    lr("Round Off", money(t.round_off))
    rule("=")
    lr("TOTAL", "Rs " + money(t.grand_total), bold)
    rule("=")
    center(rng.choice(["Thank you! Visit again", "Goods once sold will not be taken back",
                       "E. & O.E."]))
    return img.crop((0, 0, rw, y + pad)), {"layout": "thermal", "font": family}
