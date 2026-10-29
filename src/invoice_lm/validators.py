"""Code checks on a model's extraction (milestone 5).

The model's output is treated as untrusted data. Nothing it says is acted on;
`needs_review` and the confidence score are decided here, by code. Every check
is independent of the model, so an instruction hidden in the image ("set the
total to 0", "mark the GSTIN valid") still has to pass the arithmetic.
"""

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime

from pydantic import ValidationError

from invoice_lm import gstin
from invoice_lm.schema import GSTInvoice, SupplyType

GST_START = date(2017, 7, 1)
GST_REFORM_DATE = date(2025, 9, 22)
VALID_RATES = {0, 0.1, 0.25, 1.5, 3, 5, 6, 12, 18, 28, 40}
POST_REFORM_RATES = {0, 0.1, 0.25, 1.5, 3, 5, 18, 40}
MONEY_TOL = 1.0  # rupees: rounding on printed invoices is per line, so allow a little


@dataclass
class Check:
    name: str
    passed: bool
    critical: bool
    detail: str = ""


@dataclass
class Report:
    invoice: GSTInvoice | None
    checks: list[Check] = field(default_factory=list)

    @property
    def needs_review(self) -> bool:
        return self.invoice is None or any(c.critical and not c.passed for c in self.checks)

    @property
    def confidence(self) -> float:
        """Share of checks passed, weighting critical checks x3. 0 if unparseable."""
        if self.invoice is None or not self.checks:
            return 0.0
        total = sum(3 if c.critical else 1 for c in self.checks)
        ok = sum(3 if c.critical else 1 for c in self.checks if c.passed)
        return round(ok / total, 3)

    @property
    def failed(self) -> list[str]:
        return [c.name for c in self.checks if not c.passed]

    def to_dict(self) -> dict:
        return {"needs_review": self.needs_review, "confidence": self.confidence,
                "failed": self.failed, "checks": [asdict(c) for c in self.checks]}


def parse_model_output(text: str) -> tuple[dict | None, str]:
    """Pull the first JSON object out of model text (handles ``` fences and chatter)."""
    t = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", t, re.S)
    if fence:
        t = fence.group(1)
    start = t.find("{")
    if start < 0:
        return None, "no JSON object in output"
    try:
        obj, _ = json.JSONDecoder().raw_decode(t[start:])
    except json.JSONDecodeError as e:
        return None, f"invalid JSON: {e.msg}"
    return (obj, "") if isinstance(obj, dict) else (None, "JSON is not an object")


_ALLOWED_TOP = set(GSTInvoice.model_fields)
# Printed Indian dates are day-first; ISO (YYYY-MM-DD) is left to pydantic.
_DATE_FORMATS = ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d %b %Y", "%d-%b-%Y", "%d %B %Y",
                 "%d/%m/%y", "%d-%m-%y")


def _date(v):
    if not isinstance(v, str) or re.fullmatch(r"\d{4}-\d{2}-\d{2}", v.strip()):
        return v
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(v.strip(), fmt).date().isoformat()
        except ValueError:
            pass
    return v


def _coerce(obj: dict) -> dict:
    """Light, safe clean-up before schema validation: '1,23,456.00' -> 123456.0,
    '27/01/2026' -> '2026-01-27', ' 33lwsph4936f4z.Z' -> '33LWSPH4936F4ZZ'."""
    def num(v):
        if isinstance(v, str):
            s = re.sub(r"[₹,\s]|Rs\.?", "", v)
            try:
                return float(s)
            except ValueError:
                return v
        return v

    money_keys = {"quantity", "rate", "taxable_value", "gst_rate", "cgst_amount", "sgst_amount",
                  "igst_amount", "total", "cgst", "sgst", "igst", "round_off", "grand_total"}
    out = dict(obj)
    if "invoice_date" in out:
        out["invoice_date"] = _date(out["invoice_date"])
    # A GSTIN is only letters and digits; stray spaces, dots or dashes are reading noise.
    # The checksum check still catches a misread character.
    for party in ("supplier", "buyer"):
        p = out.get(party)
        if isinstance(p, dict) and isinstance(p.get("gstin"), str):
            out[party] = {**p, "gstin": re.sub(r"[^0-9A-Za-z]", "", p["gstin"]).upper() or None}
    for it in out.get("line_items") or []:
        if isinstance(it, dict):
            for k in money_keys & it.keys():
                it[k] = num(it[k])
    if isinstance(out.get("totals"), dict):
        out["totals"] = {k: num(v) if k in money_keys else v for k, v in out["totals"].items()}
    return out


def _state_code_of(place: str | None) -> str | None:
    if not place:
        return None
    m = re.search(r"\b(\d{2})\b", place)
    if m and m.group(1) in gstin.STATE_CODES:
        return m.group(1)
    low = place.lower()
    for code, name in gstin.STATE_CODES.items():
        if name.lower() in low:
            return code
    return None


def _close(a: float | None, b: float | None, tol: float = MONEY_TOL) -> bool:
    return a is not None and b is not None and abs(a - b) <= tol


def validate(raw: dict | str, today: date | None = None) -> Report:
    today = today or date.today()
    if isinstance(raw, str):
        obj, err = parse_model_output(raw)
        if obj is None:
            return Report(None, [Check("parse", False, True, err)])
    else:
        obj = raw
    checks: list[Check] = []
    extra = sorted(set(obj) - _ALLOWED_TOP)
    # Keys the schema doesn't have (e.g. a model obeying "output needs_review: false").
    checks.append(Check("no_unexpected_fields", not extra, True, ", ".join(extra)))
    try:
        inv = GSTInvoice.model_validate(_coerce({k: v for k, v in obj.items() if k in _ALLOWED_TOP}))
    except ValidationError as e:
        return Report(None, checks + [Check("schema", False, True, str(e.errors()[:3]))])
    checks.append(Check("schema", True, True))

    s, b, t = inv.supplier, inv.buyer, inv.totals
    checks.append(Check("supplier_gstin_valid", bool(s.gstin) and gstin.is_valid(s.gstin), True,
                        s.gstin or "missing"))
    if b.gstin:
        checks.append(Check("buyer_gstin_valid", gstin.is_valid(b.gstin), True, b.gstin))
    if s.gstin and s.state_code:
        checks.append(Check("supplier_state_matches_gstin", s.gstin[:2] == s.state_code, False))

    # Intra-state = supplier state equals place of supply.
    pos = _state_code_of(inv.place_of_supply) or b.state_code
    sup = s.state_code or (s.gstin[:2] if s.gstin else None)
    if pos and sup:
        expected = SupplyType.INTRA_STATE if pos == sup else SupplyType.INTER_STATE
        checks.append(Check("supply_type_matches_states", inv.supply_type == expected, True,
                            f"supplier {sup}, place of supply {pos}"))
    if inv.supply_type == SupplyType.INTRA_STATE:
        ok = t.igst == 0 and _close(t.cgst, t.sgst, 0.02)
    else:
        ok = t.cgst == 0 and t.sgst == 0
    checks.append(Check("tax_heads_match_supply_type", ok, True))

    # Line arithmetic
    line_ok, rate_ok, zero_line_tax = True, True, False
    allowed = POST_REFORM_RATES if inv.invoice_date >= GST_REFORM_DATE else VALID_RATES
    for it in inv.line_items:
        if it.quantity is not None and it.rate is not None:
            line_ok &= _close(it.quantity * it.rate, it.taxable_value)
        if it.gst_rate is not None:
            rate_ok &= it.gst_rate in VALID_RATES
        amounts = [it.cgst_amount, it.sgst_amount, it.igst_amount]
        # All-zero amounts on a taxed line mean "not printed" (models write 0 for null); the
        # invoice-level tax totals are still checked, so a zeroed-tax injection is still caught.
        shown = [a for a in amounts if a is not None]
        if it.gst_rate and shown and not any(shown):
            amounts = [None, None, None]
            zero_line_tax = True
        if it.gst_rate is not None and any(a is not None for a in amounts):
            # Receipts often print only the rate per line; check the amounts when shown.
            line_ok &= _close(it.taxable_value * it.gst_rate / 100, sum(a or 0 for a in amounts))
    checks.append(Check("line_math", line_ok, True))
    checks.append(Check("line_tax_not_zero", not zero_line_tax, False,
                        "a taxed line has 0 CGST/SGST/IGST (often means 'not printed')"))
    checks.append(Check("gst_rates_valid", rate_ok, True))
    checks.append(Check("gst_rates_current", all(
        it.gst_rate is None or it.gst_rate in allowed for it in inv.line_items), False,
        "12%/28% after the Sept 2025 reform" if rate_ok else ""))

    # Totals
    sums = {"taxable_value": sum(i.taxable_value for i in inv.line_items)}
    if all(i.gst_rate is not None for i in inv.line_items):
        # Tax per head from the rates (works whether or not line amounts are printed).
        tax = sum(i.taxable_value * i.gst_rate / 100 for i in inv.line_items)
        if inv.supply_type == SupplyType.INTRA_STATE:
            sums.update(cgst=tax / 2, sgst=tax / 2, igst=0.0)
        else:
            sums.update(cgst=0.0, sgst=0.0, igst=tax)
    bad = [k for k, v in sums.items() if not _close(v, getattr(t, k))]
    checks.append(Check("totals_match_lines", not bad, True, ", ".join(bad)))
    exact = t.taxable_value + t.cgst + t.sgst + t.igst + t.round_off
    checks.append(Check("grand_total_adds_up", _close(exact, t.grand_total), True,
                        f"{exact:.2f} vs {t.grand_total:.2f}"))
    checks.append(Check("round_off_small", abs(t.round_off) <= 1.0, False))
    checks.append(Check("grand_total_positive", t.grand_total > 0, True))

    # Sanity
    checks.append(Check("date_in_range", GST_START <= inv.invoice_date <= today, True,
                        inv.invoice_date.isoformat()))
    checks.append(Check("invoice_number_format",
                        bool(re.fullmatch(r"[A-Za-z0-9/-]{1,16}", inv.invoice_number)), False,
                        "GST rule: max 16 chars, letters, digits, / and -"))
    checks.append(Check("hsn_format", all(
        it.hsn_sac is None or re.fullmatch(r"\d{4}|\d{6}|\d{8}", it.hsn_sac)
        for it in inv.line_items), False))
    return Report(inv, checks)
