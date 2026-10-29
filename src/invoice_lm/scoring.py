"""Compare a predicted invoice with the label (milestone 6 metrics).

- Field accuracy: each scalar header field is right or wrong.
- Critical fields: supplier GSTIN, invoice number, date, tax totals, grand total.
  `critical_all_correct` is the number that matters for a tax filing.
- Line items: F1, where a predicted line counts as correct when HSN, quantity,
  taxable value and GST rate all match a label line.
"""

import re
from datetime import date

from invoice_lm.schema import GSTInvoice

HEADER_FIELDS = [
    "invoice_number", "invoice_date", "supply_type", "place_of_supply",
    "supplier.name", "supplier.gstin", "supplier.state_code",
    "buyer.name", "buyer.gstin", "buyer.state_code",
    "totals.taxable_value", "totals.cgst", "totals.sgst", "totals.igst",
    "totals.round_off", "totals.grand_total",
]
CRITICAL_FIELDS = [
    "supplier.gstin", "invoice_number", "invoice_date",
    "totals.taxable_value", "totals.cgst", "totals.sgst", "totals.igst", "totals.grand_total",
]


# Not printed on receipts, but correctly derivable from the GSTIN: not scored when absent.
DERIVABLE = {"supplier.state_code", "buyer.state_code"}


def _get(inv: GSTInvoice, path: str):
    obj = inv
    for part in path.split("."):
        obj = getattr(obj, part)
    return obj


def _norm_text(v) -> str:
    return re.sub(r"[^a-z0-9]", "", str(v).lower())


def _state(v) -> str:
    m = re.search(r"\d{2}", str(v or ""))
    return m.group(0) if m else _norm_text(v)


def same(path: str, a, b) -> bool:
    if a is None or b is None:
        return a is None and b is None
    if isinstance(b, float) or isinstance(a, float):
        try:
            return abs(float(a) - float(b)) <= 0.011
        except (TypeError, ValueError):
            return False
    if isinstance(b, date):
        return a == b
    if path == "place_of_supply":
        return _state(a) == _state(b)
    return _norm_text(a) == _norm_text(b)


def _line_key(it) -> tuple:
    return (_norm_text(it.hsn_sac), round(it.quantity or 0, 2), round(it.taxable_value, 2),
            it.gst_rate)


def score(pred: GSTInvoice | None, label: GSTInvoice) -> dict:
    """Per-document scores. A prediction that failed to parse scores 0 everywhere."""
    if pred is None:
        fields = {f: False for f in HEADER_FIELDS}
        return {"parsed": False, "fields": fields, "field_acc": 0.0,
                "critical_all_correct": False, "line_tp": 0, "line_pred": 0,
                "line_gold": len(label.line_items), "all_correct": False}
    fields = {f: same(f, _get(pred, f), _get(label, f)) for f in HEADER_FIELDS
              if not (f in DERIVABLE and _get(label, f) is None)}
    gold = [_line_key(i) for i in label.line_items]
    tp = 0
    for k in (_line_key(i) for i in pred.line_items):
        if k in gold:
            gold.remove(k)
            tp += 1
    # Rate and per-line tax amounts aren't in the line key; check them for "all correct".
    # Printed: must match. Not printed: must be null (or 0); an invented amount is an error.
    def _tax_ok(p, lab, f):
        a, b = getattr(p, f), getattr(lab, f)
        return not a if b is None else (a is not None and abs(a - b) < 0.01)
    tax_ok = len(pred.line_items) == len(label.line_items) and all(
        _tax_ok(p, lab, f) for p, lab in zip(pred.line_items, label.line_items)
        for f in ("rate", "cgst_amount", "sgst_amount", "igst_amount"))
    return {
        "parsed": True,
        "fields": fields,
        "field_acc": sum(fields.values()) / len(fields),
        "critical_all_correct": all(fields[f] for f in CRITICAL_FIELDS),
        "line_tp": tp, "line_pred": len(pred.line_items), "line_gold": len(label.line_items),
        # Everything printed was read right: a validator flag on this is a false alarm.
        "all_correct": all(fields.values()) and tp == len(pred.line_items) == len(label.line_items)
        and tax_ok,
    }


def aggregate(rows: list[dict]) -> dict:
    """rows: score() dicts, each optionally with 'needs_review' from the validators."""
    n = len(rows)
    if not n:
        return {}
    tp = sum(r["line_tp"] for r in rows)
    p = sum(r["line_pred"] for r in rows)
    g = sum(r["line_gold"] for r in rows)
    prec, rec = (tp / p if p else 0.0), (tp / g if g else 0.0)
    out = {
        "n": n,
        "parse_rate": sum(r["parsed"] for r in rows) / n,
        "field_acc": sum(r["field_acc"] for r in rows) / n,
        "critical_all_correct": sum(r["critical_all_correct"] for r in rows) / n,
        "line_f1": 2 * prec * rec / (prec + rec) if prec + rec else 0.0,
        "per_field": {f: sum(r["fields"][f] for r in rows if f in r["fields"])
                      / max(1, sum(f in r["fields"] for r in rows)) for f in HEADER_FIELDS},
    }
    if all("needs_review" in r for r in rows):
        wrong = [r for r in rows if not r["critical_all_correct"]]
        # A flag on a wrong buyer GSTIN or supply type is a correct catch, so false flags are
        # counted only on extractions where everything printed was read right.
        right = [r for r in rows if r.get("all_correct", r["critical_all_correct"])]
        # Of the documents with a wrong critical field, how many did the validators flag?
        out["validator_catch_rate"] = (sum(r["needs_review"] for r in wrong) / len(wrong)
                                       if wrong else None)
        # Of the fully correct documents, how many were flagged anyway (extra human work)?
        out["all_correct"] = len(right) / n
        out["false_flag_rate"] = (sum(r["needs_review"] for r in right) / len(right)
                                  if right else None)
        # Wrong critical field AND not flagged: the errors that would reach a tax filing.
        out["silent_error_rate"] = sum(
            (not r["critical_all_correct"]) and not r["needs_review"] for r in rows) / n
    return out
