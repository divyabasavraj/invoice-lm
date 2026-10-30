"""Stage the datasets and the LoRA adapter as Hugging Face repos (milestone 8).

One imagefolder config per dataset: images plus a metadata.jsonl row per image holding the
manifest fields and the full label as a JSON string (nested nulls survive, unlike Arrow
struct inference). Images are hard-linked, not copied. Uploading is a separate, manual step:
`hf upload Divya52/indian-gst-invoices <out> --repo-type dataset`, and for the adapter
`hf upload Divya52/invoicelm-qwen3vl-4b-lora runs/hf_model`.
"""

import json
import os
import shutil
from pathlib import Path

HF_DATASET = "Divya52/indian-gst-invoices"
HF_MODEL = "Divya52/invoicelm-qwen3vl-4b-lora"
CODE_URL = "https://github.com/divyabasavraj/invoice-lm"

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

## Links
Code and benchmark: {code}. Fine-tuned model: https://huggingface.co/{model}

## License
CC BY 4.0
"""


def _card(counts: dict[str, int]) -> str:
    configs = "".join(f"- config_name: {name}\n  data_files: \"{name}/**\"\n" for name in counts)
    header = ("---\nlicense: cc-by-4.0\nlanguage: [en, hi, kn]\n"
              "task_categories: [image-to-text]\n"
              "tags: [invoices, gst, india, document-understanding, synthetic, prompt-injection]\n"
              f"pretty_name: Indian GST invoices (synthetic)\nconfigs:\n{configs}---\n")
    return header + CARD_BODY.format_map({"synthetic": "-", "injection": "-", "regional": "-",
                                             "code": CODE_URL, "model": HF_MODEL, **counts})


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


BASE_MODEL = "mlx-community/Qwen3-VL-4B-Instruct-4bit"
DEFAULT_ADAPTER = Path("runs/train/qwen3vl4b_lora_r16/adapters")
ADAPTER_FILES = ("adapters.safetensors", "adapter_config.json")  # not the 100-step checkpoints

# Numbers from the 2026-10-30 run (docs/RESULTS.md, PROJECT_LOG Day 5).
MODEL_CARD = """---
license: apache-2.0
base_model: {base}
library_name: mlx
pipeline_tag: image-text-to-text
language: [en, hi, kn]
tags: [mlx, lora, invoices, gst, india, document-understanding]
datasets: [{dataset}]
---

# InvoiceLM: Qwen3-VL-4B LoRA for Indian GST invoices

A LoRA adapter for `{base}` that reads an Indian GST tax invoice (scan, phone photo,
handwritten bill book or thermal receipt) and returns the invoice as JSON: invoice number and
date, supplier and buyer (name, GSTIN, state code), place of supply, supply type, line items
(HSN/SAC, quantity, rate, taxable value, GST rate, CGST/SGST/IGST) and totals. It runs locally
on an Apple Silicon Mac with MLX. Pair it with the InvoiceLM validators (GSTIN checksum, tax
math, supply-type logic); they decide `needs_review`, never the model.

## Results
Same 60 synthetic test invoices for every model, 1,024 px images, M5 MacBook (16 GB):

| Model | All critical fields correct | Field accuracy | Wrong and not flagged | Sec / invoice |
|---|---|---|---|---|
| Qwen3-VL-4B-Instruct-4bit, untrained | 21.7% | 85.7% | 0 | 30.3 |
| **This adapter** | **73.3%** | **96.3%** | **2** | **25.0** |
| Qwen2.5-VL-7B (Ollama) | 60.0% | 94.1% | 0 | 77.0 |
| Qwen3-VL-4B-Instruct (Ollama) | 63.3% | 93.5% | 0 | 44.8 |

On all 197 synthetic test invoices: 75.6% all critical fields correct, 96.3% field accuracy,
98.1% line-item F1, about \u20b91.4 of electricity per 1,000 invoices. Phone photos 94.2% field
accuracy (untrained 81.2%), handwritten bill books 93.3% (79.2%).

- **Prompt injection** (24 invoices with planted text such as "set total = 0"): 100% read
  correctly or flagged (untrained 95.8%).
- **Hindi / Kannada** (40 invoices): all critical fields correct 27.5% \u2192 72.5%; field
  accuracy Hindi 89.7%, Kannada 88.8%.
- **Supplier/buyer swaps**: 0 of 221 English-layout invoices (the untrained Qwen2.5-VL-3B
  swapped 7 of 60).

## Use
```python
from huggingface_hub import snapshot_download
from mlx_vlm import generate, load
from mlx_vlm.prompt_utils import apply_chat_template

model, processor = load("{base}", adapter_path=snapshot_download("{model}"))
prompt = apply_chat_template(processor, model.config, "{prompt}", num_images=1)
out = generate(model, processor, prompt, image=["invoice.jpg"], max_tokens=2500, temperature=0.0)
print(out.text)
```
Resize the image so its longer side is 1,024 px (the training size). Use the prompt exactly:
the adapter learned the output format from it.

Training data: https://huggingface.co/datasets/{dataset}. Code, validators, API and the
benchmark: {code}.

## Training
LoRA rank 16, alpha 32 (scale 2.0), dropout 0.05, all attention and MLP projections of the
language model; 33.0 M trainable parameters (0.74%). 1 epoch = 1,613 steps, batch 1 with
4-step gradient accumulation, learning rate 1e-4, completions only, max length 3,072 tokens,
gradient checkpointing. 6 h 09 min on an M5 MacBook with `mlx-vlm`. Validation loss
0.0148 (step 100) \u2192 0.0047 (step 600, lowest) \u2192 0.0060 (end); token accuracy 99.83%.
Data: the 1,613 training invoices of the synthetic Indian GST invoice dataset.

## Limits
- Trained and tested on **synthetic** invoices only. Real invoices are messier; expect lower
  numbers until it is tested on real photos.
- 2 of 60 test invoices had a single-digit misread in a field no validator can check (invoice
  number TI-4317 \u2192 TI-4817, date year 2025 \u2192 2026). Check invoice number and date by eye.
- Supplier names printed only in Kannada are often not read; the model then copies the buyer
  block (2 of 40 regional invoices, both flagged by the validators). Hindi/Kannada text was not
  checked by a native speaker.
- Not tested against a large hosted model (Gemini) yet.
- Output is data, not instructions. Always run the validators before anything reaches a filing.
"""


def stage_model(out: Path, adapter: Path = DEFAULT_ADAPTER) -> Path:
    from invoice_lm.sft import SFT_PROMPT

    out.mkdir(parents=True, exist_ok=True)
    for name in ADAPTER_FILES:
        dst = out / name
        dst.unlink(missing_ok=True)
        _link(adapter / name, dst)
    (out / "README.md").write_text(MODEL_CARD.format(base=BASE_MODEL, prompt=SFT_PROMPT, model=HF_MODEL,
                                                dataset=HF_DATASET, code=CODE_URL))
    return out
