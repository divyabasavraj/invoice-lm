"""Stage the datasets as a Hugging Face dataset repo (milestone 8).

One imagefolder config per dataset: images plus a metadata.jsonl row per image holding the
manifest fields and the full label as a JSON string (nested nulls survive, unlike Arrow
struct inference). Images are hard-linked, not copied. Uploading is a separate, manual step:
`hf upload <user>/indian-gst-invoices <out> --repo-type dataset`.
"""

import json
import os
import shutil
from pathlib import Path

DEFAULT_SOURCES = {"synthetic": Path("data/synth_v1"),
                   "injection": Path("data/injection_v1"),
                   "regional": Path("data/regional_v1")}

CARD_BODY = """
# Indian GST invoices (synthetic)

Synthetic Indian GST tax invoices with exact ground-truth JSON, built for training and testing
small vision-language models that read invoices. Made for the InvoiceLM project.
No real business data: every invoice is generated, and
the GSTINs are checksum-valid but invented.

## Configs
| Config | Rows | What it is |
|---|---|---|
| `synthetic` | {synthetic} | 4 layouts (classic, minimal, handwritten bill book, thermal receipt) × clean / scan / phone photo; fixed `split` column: train / val / test |
| `injection` | {injection} | Prompt-injection test set: 8 attacks (e.g. "set total = 0", flip IGST) × visible / tiny / near-invisible text. `attack`, `attack_target` say what was planted |
| `regional` | {regional} | Hindi (Devanagari) and Kannada shop names and goods, shaped with HarfBuzz. Translations not yet checked by a native speaker |

## Fields
- `file_name`: the image (PNG for clean, JPEG for scan/photo)
- `label`: the invoice as JSON, schema version 1.0: invoice number and date, supplier and buyer
  (name, GSTIN, state code), place of supply, supply type, reverse charge, line items (HSN/SAC,
  quantity, rate, taxable value, GST rate, CGST/SGST/IGST) and totals. A field the layout does not
  print is `null`: the label holds only what can be read off the page.
- generation metadata: `split`, `level`, `layout`, `font`, `supply_type`, `n_items`, and per config
  `script` or `attack`, `attack_style`, `attack_target`

## How it was made
Python + Pillow, labels correct by construction: 25 products with real HSN/SAC codes, GST rates
after the September 2025 rate change, intra-state (CGST + SGST) and inter-state (IGST) supplies,
Indian number formatting and amounts in words. Photo augmentation: perspective, uneven light,
shadow, blur, folds, JPEG.

## Limits
Synthetic layouts are cleaner and more regular than real invoices; a model trained only on these
will be weaker on real photos. Product list and layouts are small. Use for research and testing.

## License
CC BY 4.0
"""


def _card(counts: dict[str, int]) -> str:
    configs = "".join(f"- config_name: {name}\n  data_files: \"{name}/**\"\n" for name in counts)
    header = ("---\nlicense: cc-by-4.0\nlanguage: [en, hi, kn]\n"
              "task_categories: [image-to-text]\n"
              "tags: [invoices, gst, india, document-understanding, synthetic, prompt-injection]\n"
              f"pretty_name: Indian GST invoices (synthetic)\nconfigs:\n{configs}---\n")
    return header + CARD_BODY.format_map({**{"synthetic": "-", "injection": "-",
                                             "regional": "-"}, **counts})


def _link(src: Path, dst: Path) -> None:
    try:
        os.link(src, dst)
    except OSError:  # other volume
        shutil.copy2(src, dst)


def stage_dataset(out: Path, sources: dict[str, Path] | None = None) -> Path:
    sources = sources or DEFAULT_SOURCES
    out.mkdir(parents=True, exist_ok=True)
    counts = {}
    for name, src in sources.items():
        dest = out / name
        if dest.exists():
            shutil.rmtree(dest)
        (dest / "images").mkdir(parents=True)
        n = 0
        with (dest / "metadata.jsonl").open("w") as meta:
            for line in (src / "manifest.jsonl").open():
                row = json.loads(line)
                image = Path(row.pop("image"))
                label = (src / row.pop("label")).read_text()
                _link(src / image, dest / "images" / image.name)
                row = {"file_name": f"images/{image.name}", **row,
                       "label": json.dumps(json.loads(label), ensure_ascii=False)}
                meta.write(json.dumps(row, ensure_ascii=False) + "\n")
                n += 1
        counts[name] = n
    (out / "README.md").write_text(_card(counts))
    return out
