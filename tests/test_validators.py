import json
import random
from datetime import date

import pytest

from invoice_lm.generator.data import random_invoice
from invoice_lm.schema import GSTInvoice
from invoice_lm.scoring import aggregate, score
from invoice_lm.validators import parse_model_output, validate

TODAY = date(2026, 10, 20)
INVOICES = [random_invoice(random.Random(f"v-{i}")) for i in range(300)]


def _dump(inv: GSTInvoice) -> dict:
    return json.loads(inv.model_dump_json())


@pytest.mark.parametrize("inv", INVOICES)
def test_true_labels_pass_every_critical_check(inv):
    rep = validate(_dump(inv), TODAY)
    assert not rep.needs_review, rep.failed


def test_labels_pass_soft_checks_too():
    soft_fail = [validate(_dump(i), TODAY).failed for i in INVOICES]
    assert all(not f for f in soft_fail), [f for f in soft_fail if f][:3]


def _mutate(fn):
    d = _dump(INVOICES[0])
    fn(d)
    return validate(d, TODAY)


def test_injected_total_zero_is_flagged():
    rep = _mutate(lambda d: d["totals"].update(grand_total=0))
    assert rep.needs_review and "grand_total_adds_up" in rep.failed


def test_injected_gstin_swap_is_flagged():
    rep = _mutate(lambda d: d["supplier"].update(gstin="29ABCDE1234F1Z5"))
    assert rep.needs_review


def test_model_setting_needs_review_is_flagged():
    rep = _mutate(lambda d: d.update(needs_review=False))
    assert rep.needs_review and "no_unexpected_fields" in rep.failed


def test_supply_type_flip_is_flagged():
    def flip(d):
        d["supply_type"] = "inter_state" if d["supply_type"] == "intra_state" else "intra_state"
    assert _mutate(flip).needs_review


def test_line_tax_zeroed_is_flagged():
    def zero(d):
        for it in d["line_items"]:
            for k in ("cgst_amount", "sgst_amount", "igst_amount"):
                if it[k] is not None:
                    it[k] = 0
    # Totals are still right, so this is a minor check (lower confidence), not a forced review:
    # models write 0 for line amounts the invoice doesn't print. Zeroed totals are critical.
    rep = _mutate(zero)
    assert "line_tax_not_zero" in rep.failed and rep.confidence < 1


def test_future_date_is_flagged():
    assert "date_in_range" in _mutate(lambda d: d.update(invoice_date="2027-01-01")).failed


def test_indian_formatted_strings_are_coerced():
    def fmt(d):
        d["totals"]["grand_total"] = f"Rs. {d['totals']['grand_total']:,.2f}"
    assert not _mutate(fmt).needs_review


@pytest.mark.parametrize("text,ok", [
    ('```json\n{"a": 1}\n```', True),
    ('Here is the data: {"a": {"b": 2}} hope this helps', True),
    ("no json here", False),
    ('{"a": ', False),
])
def test_parse_model_output(text, ok):
    obj, _ = parse_model_output(text)
    assert (obj is not None) == ok


def test_unparseable_output_needs_review_with_zero_confidence():
    rep = validate("sorry, I can't read this", TODAY)
    assert rep.needs_review and rep.confidence == 0 and rep.invoice is None


def test_perfect_prediction_scores_one():
    s = score(INVOICES[1], INVOICES[1])
    assert s["field_acc"] == 1 and s["critical_all_correct"] and s["line_tp"] == s["line_gold"]


def test_wrong_total_breaks_critical_and_counts_as_caught():
    pred = INVOICES[2].model_copy(deep=True)
    pred.totals.grand_total += 100
    rep = validate(_dump(pred), TODAY)
    s = score(rep.invoice, INVOICES[2]) | {"needs_review": rep.needs_review}
    ok = score(INVOICES[3], INVOICES[3]) | {"needs_review": False}
    agg = aggregate([s, ok])
    assert not s["critical_all_correct"]
    assert agg["validator_catch_rate"] == 1 and agg["silent_error_rate"] == 0
    assert agg["false_flag_rate"] == 0


def test_missing_prediction_scores_zero():
    s = score(None, INVOICES[0])
    assert s["field_acc"] == 0 and not s["parsed"]


@pytest.mark.parametrize("layout", ["classic", "minimal", "handwritten", "thermal"])
def test_printed_labels_pass_validators(layout):
    from invoice_lm.generator.render import printed_label

    for inv in INVOICES[:50]:
        rep = validate(_dump(printed_label(inv, layout)), TODAY)
        assert not rep.needs_review, (layout, rep.failed)


def test_thermal_label_hides_unprinted_fields():
    from invoice_lm.generator.render import printed_label

    lab = printed_label(INVOICES[0], "thermal")
    assert lab.buyer.state_code is None and all(i.cgst_amount is None for i in lab.line_items)
    assert all(i.total is None for i in printed_label(INVOICES[0], "classic").line_items)


def test_decoding_schema_requires_every_field():
    from invoice_lm.schema import decoding_schema

    s = decoding_schema()
    for o in [s, *s["$defs"].values()]:
        if "properties" in o:
            assert set(o["required"]) == set(o["properties"])
    assert {"type": "null"} in s["properties"]["place_of_supply"]["anyOf"]
    assert "default" not in str(s)


def test_printed_dates_are_coerced_day_first():
    from invoice_lm.validators import _date

    assert _date("27/01/2026") == "2026-01-27"
    assert _date("05-04-2025") == "2025-04-05"
    assert _date("05 Apr 2025") == "2025-04-05"
    assert _date("05-04-25") == "2025-04-05"
    assert _date("2026-01-27") == "2026-01-27"
    assert _date("2701-02-26") == "2701-02-26"  # garbage stays garbage, the date check fails it


def test_zero_line_tax_means_not_printed_but_zeroed_totals_still_caught():
    import json, random
    from invoice_lm.generator.data import random_invoice
    from invoice_lm.validators import validate

    inv = random_invoice(random.Random("zero-tax"))
    d = json.loads(inv.model_dump_json())
    taxed = [it for it in d["line_items"] if it["gst_rate"]]
    assert taxed
    for it in d["line_items"]:
        it["cgst_amount"] = it["sgst_amount"] = it["igst_amount"] = 0
    assert "line_math" not in validate(d).failed and "line_tax_not_zero" in validate(d).failed
    d["totals"]["cgst"] = d["totals"]["sgst"] = d["totals"]["igst"] = 0
    assert validate(d).needs_review


def test_invented_line_tax_is_not_all_correct():
    import random
    from invoice_lm.generator.data import random_invoice
    from invoice_lm.generator.render import printed_label
    from invoice_lm.scoring import score

    label = printed_label(random_invoice(random.Random("thermal")), "thermal")
    assert score(label, label)["all_correct"]
    pred = label.model_copy(deep=True)
    for it in pred.line_items:
        it.cgst_amount = 0.0
    assert score(pred, label)["all_correct"]  # 0 reads as "not printed"
    pred.line_items[0].cgst_amount = 2734.83
    assert not score(pred, label)["all_correct"]


def test_misread_rate_is_not_all_correct():
    # inj_009: rate 8,829 read as 829 while the line's taxable value was right. line_math
    # caught it, so the flag is a real catch, not a false alarm.
    pred = INVOICES[0].model_copy(deep=True)
    pred.line_items[0].rate = (pred.line_items[0].rate or 0) + 8000
    s = score(pred, INVOICES[0])
    assert s["line_tp"] == s["line_gold"]  # the line key (and F1) ignores rate
    assert not s["all_correct"]


def test_gstin_punctuation_is_cleaned_but_checksum_still_applies():
    # syn_0_00074: a handwritten photo read as "33LWSPH4936F4Z.Z" (stray dot).
    d = _dump(INVOICES[0])
    good = d["buyer"]["gstin"]
    d["buyer"]["gstin"] = f" {good[:5].lower()} {good[5:13]}.{good[13:]}-"
    assert not validate(d, TODAY).needs_review
    d["buyer"]["gstin"] = good[:14] + ("A" if good[14] != "A" else "B")  # a real misread
    assert "buyer_gstin_valid" in validate(d, TODAY).failed
