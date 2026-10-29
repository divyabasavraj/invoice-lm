import random

from PIL import Image, ImageFont

from invoice_lm.generator.regional import GOODS, regional_invoice
from invoice_lm.generator.render import printed_label, render
from invoice_lm.generator.shape import ShapedDraw, has_indic, runs, shape
from invoice_lm.validators import validate


def test_runs_split_scripts():
    assert runs("To: श्री गणेश Pvt Ltd") == [("To: ", None), ("श्री गणेश", "deva"), (" Pvt Ltd", None)]
    assert runs("ಬಾಲ್ ಪೆನ್ (50ರ ಡಬ್ಬಿ)")[0] == ("ಬಾಲ್ ಪೆನ್", "knda")
    assert not has_indic("Rs. 1,250")


def test_harfbuzz_forms_conjuncts():
    # श्री is 4 code points (श ् र ी) but shapes to fewer glyphs: the conjunct is formed.
    assert len(shape("श्री", "deva", 28)) < 4
    assert len(shape("ಲಕ್ಷ್ಮೀ", "knda", 28)) < len("ಲಕ್ಷ್ಮೀ")


def test_shaped_draw_paints_and_measures():
    img = Image.new("RGB", (600, 80), "white")
    d = ShapedDraw(img)
    f = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 28)
    d.text((10, 10), "Item: बासमती चावल", font=f, fill=(0, 0, 0))
    w = d.textlength("Item: बासमती चावल", font=f)
    assert w > d.textlength("Item: ", font=f) + 50
    ink = [x for x in range(600) if any(img.getpixel((x, y)) != (255, 255, 255) for y in range(80))]
    assert ink and abs(max(ink) - (10 + w)) < 12


def test_regional_labels_valid_and_rendered():
    for i in range(40):
        rng = random.Random(f"t-{i}")
        inv, script = regional_invoice(rng, "deva" if i % 2 else "knda")
        assert has_indic(inv.supplier.name)
        local = set(GOODS[script].values())
        assert all(it.description in local or not has_indic(it.description) for it in inv.line_items)
        img, settings = render(inv, rng)
        rep = validate(printed_label(inv, settings["layout"]).model_dump(mode="json"))
        assert not rep.needs_review, rep.failed
