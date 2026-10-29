# InvoiceLM

A small vision-language model, fine-tuned on a laptop, that reads Indian GST invoices (including phone photos) into validated JSON, runs fully locally, and checks its own arithmetic before anything reaches a tax filing.

Status: work in progress. See [PLAN.md](PLAN.md), the [project log](docs/PROJECT_LOG.md) and [results](docs/RESULTS.md).

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
eval/train_lora.sh mlx-community/Qwen2.5-VL-3B-Instruct-4bit  # LoRA on Apple silicon
eval/overnight.sh <mlx model> <run name>                      # LoRA + before/after eval + report
nohup eval/when_plugged_in.sh > runs/logs/watcher.log 2>&1 &  # same chain, starts on mains power
uv run invoice-lm stage-hf                                    # Hugging Face dataset folder in runs/hf_dataset
uv run --extra api invoice-lm serve                           # API + demo page on :8000
uv run python -m invoice_lm.report                            # results table
uv run pytest
```

## API
`POST /extract` (multipart `file`) returns the invoice, `needs_review`, confidence, every check, warnings and timing. `GET /` is a one-page demo. The model backend is set with `INVOICE_LM_BACKEND` (default `ollama:qwen2.5vl:3b`). Logs carry check names and timings, never invoice contents. The demo page writes model output with `textContent` only, because text copied out of an image is untrusted.

## Budget
₹0: local models (Ollama, MLX), Gemini free tier only on synthetic data.
