import random

import pytest

from invoice_lm import gstin
from invoice_lm.generator.data import random_invoice
from invoice_lm.generator.render import amount_in_words, inr, render
from invoice_lm.schema import GSTInvoice, SupplyType


@pytest.mark.parametrize("g", ["27AAPFU0939F1ZV", "33GSPTN0231G1ZM"])
def test_published_gstins_pass_checksum(g):
    assert gstin.is_valid(g)


@pytest.mark.parametrize("g", ["27AAPFU0939F1ZA", "99AAPFU0939F1ZV", "27AAPFU0939F1Z", "27aapfu0939f1zv"])
def test_bad_gstins_fail(g):
    assert not gstin.is_valid(g)


def test_inr_grouping():
    assert inr(0) == "0.00"
    assert inr(999.5) == "999.50"
    assert inr(131986) == "1,31,986.00"
    assert inr(12345678.9) == "1,23,45,678.90"
    assert inr(-0.16) == "-0.16"


def test_amount_in_words():
    assert amount_in_words(160295) == "Rupees One Lakh Sixty Thousand Two Hundred Ninety Five Only"
    assert amount_in_words(10_00_00_000) == "Rupees Ten Crore Only"


INVOICES = [random_invoice(random.Random(i)) for i in range(500)]


@pytest.mark.parametrize("inv", INVOICES[:200] + INVOICES[200::10])
def test_label_is_internally_consistent(inv: GSTInvoice):
    t = inv.totals
    assert gstin.is_valid(inv.supplier.gstin)
    assert inv.buyer.gstin is None or gstin.is_valid(inv.buyer.gstin)
    assert inv.supplier.gstin[:2] == inv.supplier.state_code
    intra = inv.supplier.state_code == inv.buyer.state_code
    assert inv.supply_type == (SupplyType.INTRA_STATE if intra else SupplyType.INTER_STATE)
    for it in inv.line_items:
        assert it.taxable_value == pytest.approx(it.quantity * it.rate, abs=0.01)
        tax = it.taxable_value * it.gst_rate / 100
        if intra:
            assert it.igst_amount is None and it.cgst_amount == it.sgst_amount
            assert it.cgst_amount + it.sgst_amount == pytest.approx(tax, abs=0.011)
        else:
            assert it.cgst_amount is None and it.igst_amount == pytest.approx(tax, abs=0.006)
    assert t.taxable_value == pytest.approx(sum(i.taxable_value for i in inv.line_items), abs=0.01)
    assert t.grand_total == round(t.grand_total)
    assert t.taxable_value + t.cgst + t.sgst + t.igst + t.round_off == pytest.approx(t.grand_total, abs=0.01)
    assert abs(t.round_off) <= 0.5


def test_label_roundtrips_through_json():
    inv = INVOICES[0]
    assert GSTInvoice.model_validate_json(inv.model_dump_json()) == inv


def test_generation_is_reproducible():
    assert random_invoice(random.Random("0-7")) == random_invoice(random.Random("0-7"))


def test_every_layout_and_font_fits_on_the_page():
    # The largest invoices are the ones that can overflow.
    big = sorted(INVOICES, key=lambda i: len(i.line_items))[-20:]
    for layout in ("classic", "minimal"):
        for family in ("helvetica", "arial", "times", "courier"):
            for inv in big[:5]:
                img, _ = render(inv, random.Random(0), layout, family)
                assert img.size == (1240, 1754)


def test_handwritten_and_thermal_render():
    inv = max(INVOICES, key=lambda i: len(i.line_items))
    for layout in ("handwritten", "thermal"):
        img, settings = render(inv, random.Random(1), layout)
        assert settings["layout"] == layout and img.width > 500


@pytest.mark.parametrize("level", ["clean", "scan", "photo"])
def test_augment_levels(level):
    from invoice_lm.generator.augment import augment

    img, _ = render(INVOICES[0], random.Random(0), "classic", "arial")
    out = augment(img, random.Random(0), level)
    assert out.mode == "RGB" and min(out.size) > 500


def test_splits_are_stable_when_dataset_grows(tmp_path):
    import json

    from invoice_lm.generator.build import build

    small = [json.loads(x) for x in build(tmp_path / "a", 6).open()]
    big = [json.loads(x) for x in build(tmp_path / "b", 9).open()]
    assert [r["split"] for r in small] == [r["split"] for r in big[:6]]


def test_injection_set_shape(tmp_path):
    import json

    from invoice_lm.generator.build import build_injection_set

    rows = [json.loads(x) for x in build_injection_set(tmp_path).open()]
    assert len(rows) == 24 and {r["split"] for r in rows} == {"test"}
    assert len({(r["attack"], r["attack_style"]) for r in rows}) == 24
