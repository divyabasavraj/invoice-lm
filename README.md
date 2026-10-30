# InvoiceLM

A small vision-language model, fine-tuned on a laptop, that reads Indian GST invoices (including phone photos) into validated JSON, runs fully locally, and checks its own arithmetic before anything reaches a tax filing.

A LoRA fine-tune of Qwen3-VL-4B (6 h on an M5 MacBook) gets every critical field right on 73% of test invoices, against 60% for Qwen2.5-VL-7B, and runs 3× faster (25 s vs 77 s per invoice).

Status: model trained and evaluated on synthetic data; Gemini baseline and a real-photo test still to do. See [PLAN.md](PLAN.md), the [project log](docs/PROJECT_LOG.md) and [full results](docs/RESULTS.md).

## Results
Same 60 synthetic test invoices for every model, 1,024 px, all local on a 16 GB M5 MacBook:

| Model | All critical fields correct | Field accuracy | Wrong and not flagged | Sec / invoice |
|---|---|---|---|---|
| Qwen3-VL-4B-Instruct-4bit (MLX), untrained | 21.7% | 85.7% | 0 | 30.3 |
| **Qwen3-VL-4B + InvoiceLM LoRA** | **73.3%** | **96.3%** | **2** | **25.0** |
| Qwen2.5-VL-7B (Ollama) | 60.0% | 94.1% | 0 | 77.0 |
| Qwen3-VL-4B-Instruct (Ollama) | 63.3% | 93.5% | 0 | 44.8 |
| Qwen2.5-VL-3B (Ollama) | 55.0% | 89.1% | 1 | 31.6 |

"Critical" = invoice number, date, both GSTINs, supply type, place of supply and the tax totals. "Wrong and not flagged" = a critical field is wrong and no validator caught it, so it would reach a filing.

What the fine-tune changed, untrained → fine-tuned:
- phone photos 81.2% → 94.2% field accuracy; handwritten bill books 79.2% → 93.3%
- Hindi / Kannada invoices: all critical fields correct 27.5% → 72.5%
- prompt-injection invoices read correctly or flagged: 95.8% → 100% (24 invoices, 8 attacks)
- supplier/buyer swaps: 0 of 221 English-layout invoices (Qwen2.5-VL-3B swapped 7 of 60)
- validators: 0% false flags on correct extractions for every model

## Limits
- Everything above is on **synthetic** invoices. Real ones are messier; a real-photo test is next.
- The fine-tune's 2 unflagged errors are single-digit misreads in fields no check can verify (invoice number TI-4317 → TI-4817; year 2025 → 2026). Invoice number and date still need a human glance.
- Supplier names printed only in Kannada are often missed; the model then copies the buyer block (2 of 40, both flagged). The Hindi/Kannada text has not been checked by a native speaker.
- No hosted-model (Gemini) comparison yet.

## Pipeline
```
upload ─▶ intake checks ─▶ small VLM (local) ─▶ JSON ─▶ validators (code) ─▶ result + confidence + needs_review
```
Intake checks run on the bytes before the model sees anything: file type from its signature (JPG, PNG, PDF only), 10 MB, 40 MP read from the header (decompression bombs), PDFs ≤ 5 pages rendered to pixels with no scripts run, and a blur/darkness/size gate that asks for a retake instead of guessing.
The model's output is data. `needs_review` is decided by code (GSTIN checksum, state codes, CGST/SGST vs IGST, line and total arithmetic, GST slab, dates), never by the model, so an instruction hidden in an invoice image can't switch the checks off.

## Synthetic dataset
`invoice-lm generate` draws GST invoices whose labels are correct by construction:
- 25 products with real HSN/SAC codes; GST rates follow the Sept 2025 rate change (GST 2.0)
- intra-state (CGST + SGST) and inter-state (IGST), valid GSTINs, Indian number format, amount in words
- 4 layouts: classic, minimal, handwritten bill book, thermal receipt; 4 print fonts + 3 handwriting fonts
- 3 difficulty levels: clean, scan, phone photo (perspective, uneven light, shadow, blur, fold, JPEG)
- fixed train / val / test split per sample, stable as the dataset grows
- labels contain only what the layout prints (anything not shown is `null`)
- a 24-invoice prompt-injection test set (8 attacks × visible / tiny / near-invisible text)
- a 40-invoice Hindi / Kannada test set (shop names and goods in the local script), shaped with HarfBuzz so conjuncts render correctly without system libraries

## Commands
```bash
uv run invoice-lm generate --n 2000 --out data/synth_v1      # dataset
uv run invoice-lm generate --injection --out data/injection_v1
uv run invoice-lm generate --regional --n 40 --out data/regional_v1
uv run invoice-lm baseline ollama:qwen2.5vl:7b --data data/synth_v1   # zero-shot run + scores
uv run invoice-lm baseline gemini:gemini-2.5-flash --limit 50         # needs GEMINI_API_KEY
uv run invoice-lm export-sft                                  # mlx-vlm training files
eval/run_baselines.sh 1                                       # pass 1 on 3 local models (~2 h)
eval/train_lora.sh mlx-community/Qwen3-VL-4B-Instruct-4bit qwen3vl4b_lora_r16  # LoRA on Apple silicon
eval/overnight.sh <mlx model> <run name>                      # LoRA + before/after eval + report
nohup eval/when_plugged_in.sh > runs/logs/watcher.log 2>&1 &  # same chain, starts on mains power
uv run invoice-lm stage-hf                                    # Hugging Face dataset folder in runs/hf_dataset
uv run invoice-lm stage-hf-model                              # LoRA adapter + model card in runs/hf_model
uv run --extra api --extra train invoice-lm serve             # API + demo page on :8000 (fine-tune)
uv run python -m invoice_lm.report                            # results table
uv run python eval/count_swaps.py                             # supplier/buyer swaps per run
uv run pytest
```

## API
`POST /extract` (multipart `file`) returns the invoice, `needs_review`, confidence, every check, warnings and timing. `GET /` is a one-page demo. The model backend is set with `INVOICE_LM_BACKEND`; by default it is the LoRA fine-tune (`mlx:` Qwen3-VL-4B-Instruct-4bit + `runs/train/qwen3vl4b_lora_r16/adapters`, needs `--extra train`), or `ollama:qwen3-vl:4b-instruct` when the adapter isn't on disk. Responses name the backend without local paths. Logs carry check names and timings, never invoice contents. The demo page writes model output with `textContent` only, because text copied out of an image is untrusted.

## Training
LoRA rank 16 on all attention and MLP projections of the language model (33 M trainable parameters, 0.74%), one epoch of 1,613 synthetic invoices, `mlx-vlm` on the laptop: 6 h 09 min. Validation loss bottomed at step 600 (0.0047) and stayed flat, so a second epoch was not run.

## Budget
₹0: local models (Ollama, MLX), Gemini free tier only on synthetic data. Electricity for the fine-tune's inference: about ₹1.4 per 1,000 invoices.
