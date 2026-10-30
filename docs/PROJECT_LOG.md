# InvoiceLM project log

A day-by-day record of everything done on the project: each step, why it was done, what came out, and what broke.
Decisions and failures are tagged so they are easy to find for interview prep.

**Tags:** `[DECISION]` a choice and its reason · `[FAILURE]` something that went wrong and how it was fixed · `[RESULT]` a measured number · `[NEXT]` open work

**How each day is written**
```
## Day N: YYYY-MM-DD: <one-line theme>
**Goal for the day:** ...
### Steps
1. HH:MM  What was done. Why. Result. Files touched.
### Results / Decisions / Failures (only if any)
### End of day
- Done: ...  - Not done: ...  - Next: ...
```

---

## Day 1: 2026-10-20: Plan, schema, dataset v1, validators, baseline harness (milestones 1, 2, 5; 3 and 4 prepared)
**Goal for the day:** close the plan (budget, security), define the JSON the model must produce, and get the first synthetic GST invoices with correct labels on disk. Second session (from 21:18): pull the planned Day 2–3 work into today: realistic images, more layouts, splits, validators, scoring, baseline runner, fine-tuning prep.

### Steps
1. 11:19  `[DECISION]` Baselines switched from GPT/Claude to Gemini free tier + a larger local VLM via Ollama, because the budget is ₹0. Paid API prices are only quoted in the cost comparison. Files: `PLAN.md` §4.
2. 11:22  Added upload security (size, file-signature check, PDF page cap, decompression-bomb limit, PDF safe mode) and §7.1 prompt injection inside the image (5–10 injected invoices; `needs_review` is set by code, never by the model). Files: `PLAN.md` §7.
3. 11:31  Portfolio README: InvoiceLM's place in "the thread" and the daily block schedule (afternoon = generator/validators, overnight = fine-tuning). Target finish ~Nov 1–3.
4. 21:11  Started the build block. Project was a bare `uv init` (no code, no log). Checked the machine: no Chrome/Chromium installed; macOS fonts available (Helvetica, Arial, Times, Courier New, Noto Sans Kannada, Devanagari MT).
5. 21:12  `[DECISION]` Render invoices with **Pillow**, not HTML/Jinja → headless browser as the plan said. No browser is installed, a Playwright Chromium download is ~150 MB of extra tooling, and drawing directly gives exact control of every text position (useful later for word boxes). HTML templates can still be added later if layout variety needs it.
6. 21:12  `uv add pydantic pillow`, `uv add --dev pytest`. Checked Pillow's `raqm` (complex-script shaping): **not available**. Without raqm, Pillow draws Devanagari/Kannada with broken conjuncts, so regional-language invoices need a different renderer (raqm build, or a browser). This feeds the open "which regional languages in v1" decision.
7. 21:13  Wrote the output schema (milestone 1): `GSTInvoice` → `Party` (supplier, buyer), `LineItem`, `Totals`, `SupplyType` (intra_state = CGST+SGST, inter_state = IGST). `extra="forbid"`, money rounded to 2 decimals, fields not printed on the invoice are `null` (never guessed). `invoice-lm schema` prints the JSON schema for the baselines. Files: `src/invoice_lm/schema.py`, `src/invoice_lm/__init__.py`.
8. 21:13  Wrote GSTIN module: format regex, 36 state codes, mod-36 check character, random valid GSTIN from a random PAN. Verified against two published GSTINs (`27AAPFU0939F1ZV`, `33GSPTN0231G1ZM`): both pass; a one-character change fails. Shared with milestone 5 validators. Files: `src/invoice_lm/gstin.py`.
9. 21:14  Wrote invoice data generator: 26 products with real HSN/SAC codes and GST slabs (0/5/12/18/28%), 10 states, 65% intra-state, 1–8 line items, 4 invoice-number styles, FY-aware numbering, 10% unregistered buyers, grand total rounded to the rupee with a round-off line. All numbers computed in code, so labels are correct by construction. Files: `src/invoice_lm/generator/data.py`.
10. 21:14  Wrote renderer (2 layouts: `classic` bordered table, `minimal` rules only; 4 fonts; 4 accent colours; 3 date formats; Indian digit grouping `1,31,986.00`; amount in words with lakh/crore) and dataset builder (`images/`, `labels/`, `manifest.jsonl`, one RNG per sample so sample *i* never changes when *n* changes). Files: `generator/render.py`, `generator/build.py`.
11. 21:15  Smoke test: `uv run invoice-lm generate --n 50` → 50 images in 3.7 s. Looked at the images. `[FAILURE]` Three problems (see Failures #1).
12. 21:15  Fixed column headers, numeric alignment, PIN codes; regenerated and rechecked: clean.
13. 21:16  Wrote `tests/test_generator.py`: published GSTINs pass / corrupted ones fail, Indian number format, amount in words, label consistency on 500 random invoices (GSTINs valid, state code matches GSTIN, supply type matches states, line tax math, totals, round-off ≤ 0.50), JSON round-trip, reproducibility, every layout × font fits on the page. **241 passed in 0.48 s.**
14. 21:16  Rendered the widest case (Courier font, classic layout, 8 intra-state items). `[FAILURE]` More overlaps (see Failures #2). Fixed, tests still 241/241, re-rendered: clean.
15. 21:17  Generated `data/synth_v0` (200 invoices). Results below.
16. 21:18  Wrote this log; ticked milestone 1 in `PLAN.md`, marked milestone 2 in progress; updated portfolio README status.

**Second session: two days of work in one evening**

17. 21:18  Checked the machine: Ollama has `qwen2.5vl:7b` (larger local baseline) and `llama3.2-vision:11b`; 80% memory free; no `GEMINI_API_KEY` set. Started pulling `qwen2.5vl:3b` and `qwen3-vl:4b` (small-model candidates) in the background.
18. 21:19  Wrote phone-photo effects: 3 levels. `scan` = ±1.5° skew, grey paper, speckle, JPEG 55–80. `photo` = perspective tilt on a table-coloured background, light falloff, hand/phone shadow, colour tint, fold line, small rotation, blur, downscale to 60–85%, JPEG 35–70. Files: `generator/augment.py`.
19. 21:20  Added layouts: `handwritten` (printed bill-book form, values in Bradley Hand / Chalkboard / Comic Sans with blue ink and position wobble), `thermal` (80 mm shop receipt, monospace, stacked items, plain or Indian number format) and a coloured header band (30% of A4 invoices). Looked at a sample of each plus a photo: all readable and realistic. Files: `generator/render.py`.
20. 21:21  `[DECISION]` GST rates now depend on the invoice date. The GST 2.0 change on 22 Sep 2025 removed most 12% and 28% rates, and our dates run Apr 2025 – Sep 2026, so a flat table would have produced impossible invoices. Changed: paper 12→18, cartons 12→5, cement 28→18, AC 28→18, medicines 12→5, footwear by price band. Dropped LED bulbs (unsure of the new rate). Rates must be checked against CBIC notifications before the dataset is published. Files: `generator/data.py`.
21. 21:22  Wrote validators (milestone 5): parse (handles ``` fences and chatter), unexpected keys (catches a model obeying "output needs_review: false"), schema, GSTIN checksums, state code vs GSTIN, supply type vs states, tax heads vs supply type, line maths, valid and current GST slabs, totals vs lines, grand total adds up, round-off ≤ ₹1, date between 1 Jul 2017 and today, invoice number ≤ 16 characters (GST rule), HSN format. Critical failures → `needs_review`; confidence = weighted share of passed checks. Light coercion: "Rs. 1,23,456.00" → 123456.0. Files: `validators.py`.
22. 21:23  Wrote scoring (milestone 6 metrics): 16 header fields, critical-field set (supplier GSTIN, number, date, tax totals, grand total), line-item F1 (HSN + qty + taxable value + rate must all match), validator catch rate, false-flag rate, and **silent error rate** (wrong critical field AND not flagged = what would reach a tax filing). Files: `scoring.py`.
23. 21:24  Wrote the baseline runner (milestone 3): Ollama (JSON-schema constrained output, temperature 0, thinking off) and Gemini (REST, key in a header, not the URL); every raw answer cached under `runs/`, so reruns and free-tier limits cost nothing; breakdowns by level, layout and attack. CLI `invoice-lm baseline`. Files: `baseline.py`.
24. 21:25  Wrote the injection set (plan §7.1): 8 attacks (total = 0, GSTIN swap, "needs_review: false", IGST flip, double total, buyer rename, JSON break-out, all tax = 0) × 3 styles (visible note, 9 px text, near-white text) = 24 test-only invoices. The label is the true invoice. Files: `generator/inject.py`, `generator/build.py`.
25. 21:26  Tests: validators accept 300 true labels with no failures, and flag total = 0, GSTIN swap, an extra `needs_review` key, supply-type flip, zeroed line tax and a future date; scoring sanity; split stability; injection set shape. **563 passed.**
26. 21:28  Built `data/synth_v1` (2,000 invoices, 273 s, 443 MB) and `data/injection_v1` (24). Train / val / test = 1,613 / 190 / 197.
27. 21:29  Smoke test: `qwen2.5vl:3b` on 2 test invoices worked end to end (27 s and 13 s).
28. 21:29  Started all baselines. `[FAILURE]` Found a label bug and stopped the run after ~1 minute (Failures #3). Fixed it, rewrote all 2,024 labels in place (no re-render: each invoice is the first draw from its RNG, and number and totals were asserted equal), **568 tests pass**, and restarted the baselines.
29. 21:30  `[FAILURE]` (small) Restarted with `&`/`disown`, so no completion notice would arrive. Killed it and relaunched as a tracked background job.
30. 21:31  Fine-tuning prep (milestone 4): installed `mlx-vlm` 0.7.9 (MLX 0.32.4) as an optional `train` extra and read its trainer. It expects a folder with `train.jsonl` / `validation.jsonl` of `{images, messages}`. Wrote `invoice-lm export-sft`: images downscaled to 1,024 px on the long side (a full A4 page is ~2,800 vision tokens, too many for LoRA in 16 GB), short prompt, compact target JSON with nulls kept. Export: 1,613 train + 190 val in 32 s. Target length (Qwen tokenizer): median 506, p95 943, max 990 tokens. Files: `sft.py`.
31. 21:32  Wrote `eval/train_lora.sh` (LoRA r16 / α32, lr 1e-4, batch 1 × accumulation 4, 800 iters ≈ 2 epochs, max sequence 3,072, gradient checkpointing, loss on the answer only; unloads Ollama models first) and an `mlx:` backend so the fine-tuned model is scored by the same harness, on images resized the same way. Started downloading `mlx-community/Qwen2.5-VL-3B-Instruct-4bit` and `Qwen3-VL-4B-Instruct-4bit`. Files: `eval/train_lora.sh`, `baseline.py`.
32. 21:33  Wrote `report.py` (results tables → `docs/RESULTS.md`) and the project `README.md`.
33. 21:34  Timing check: 18.7 s per invoice on the 3B model. Estimate: pass 1 (60 test + 24 injected × 3 models) ~2 h; full test set ~3 h more; LoRA ~2–3 h (not measured). Too long for tonight.
34. 21:35  `[DECISION]` Stopped for the day: baseline run, model download and monitor all stopped, Ollama model unloaded. 15 cached `qwen2.5vl:3b` answers kept (the cache resumes from them).
35. 21:36  Scored the 15 cached answers (no model calls) and inspected them (Results, Failures #4).

### Results
`[RESULT]` Synthetic set v0 (`data/synth_v0`, seed 0, clean renders, no augmentation yet):

| Metric | Value |
|---|---|
| Invoices | 200 |
| Generation time | 13.2 s (~66 ms per invoice, single core) |
| Disk | 23 MB (~115 KB per PNG, 1240×1754 = A4 at 150 dpi) |
| Layouts | classic 98 · minimal 102 |
| Fonts | Helvetica 58 · Times 56 · Courier 48 · Arial 38 |
| Supply type | intra-state 128 · inter-state 72 |
| Line items | 1: 17 · 2: 52 · 3: 58 · 4: 19 · 5: 25 · 6: 14 · 8: 15 |
| Tests | 241 passed, 0.48 s |

`[RESULT]` Dataset v1 (`data/synth_v1`, seed 0):

| Metric | Value |
|---|---|
| Invoices | 2,000 (train 1,613 · val 190 · test 197) + 24 injected (test only) |
| Generation time | 273 s (~137 ms per invoice; photo effects are the slow part) |
| Disk | 443 MB (+ SFT copies at 1,024 px) |
| Difficulty | clean 599 · scan 600 · photo 801 |
| Layouts | classic 716 · minimal 599 · thermal 381 · handwritten 304 |
| Test split | clean 57 · scan 57 · photo 83; classic 71 · minimal 62 · thermal 35 · handwritten 29 |
| Tests | 568 passed |

`[RESULT]` **Preliminary only, 15 test invoices**: `qwen2.5vl:3b` zero-shot, Ollama:

| Parsed | Field acc | Critical all correct | Line F1 | Validators caught | Silent errors | Sec/invoice |
|---|---|---|---|---|---|---|
| 100% | 60.9% | 0% | 0% | 100% | 0% | 20.1 |

By difficulty, field accuracy: clean 67.3% · scan 68.8% · photo 56.2%. Worst fields: invoice date 0%, place of supply 0%, round-off 7%, CGST/SGST totals 33%. Too few invoices to quote, but two patterns are clear (Failures #4).

### Decisions
- `[DECISION]` Pillow renderer instead of HTML + headless browser (step 5).
- `[DECISION]` Schema: `null` for anything not printed; separate `supply_type` field so the CGST/SGST vs IGST rule can be checked by code. `needs_review` and confidence are **not** in the model's schema: they are added by validators (plan §7.1).
- `[DECISION]` One RNG per sample seeded with `"{seed}-{i}"`, so the test split stays fixed as the dataset grows.
- `[DECISION]` Date-aware GST rates (step 20).
- `[DECISION]` Labels hold only what the layout prints (Failures #3). The model learns to read, not to calculate; the validators do the calculating.
- `[DECISION]` State codes aren't scored when the invoice doesn't print them (they can be read off the GSTIN); every other unprinted field must be `null`.
- `[DECISION]` Fine-tuning images capped at 1,024 px (step 30). Baselines currently get full-resolution images, so there is one difference between baseline and fine-tuned runs: report it, or rerun the baselines at 1,024 px too.
- `[DECISION]` Base model not picked yet: wait for the pass 1 baseline numbers (qwen2.5vl:3b vs qwen3-vl:4b).

### Failures
1. `[FAILURE]` First renders: (a) bold table headers wider than their columns ("GST%CGST", "HSN/SACQty"); (b) in the minimal layout, quantity and unit ran together ("1 MONTH") and numeric headers were left-aligned over right-aligned numbers; (c) PIN codes didn't match the city (New Delhi – 779807). **Cause:** fixed column widths sized for the body font, and PINs drawn from one national range. **Fix:** smaller bold header font, right-aligned headers on numeric columns, wider Unit column, per-state PIN prefix ranges (Delhi 110xxx, Karnataka 560–591…). **Lesson:** look at the images, not just the labels; tests checked the numbers but nothing checked how they looked.
2. `[FAILURE]` Courier (monospace, wider) still overlapped: "Place of Supply:Rajasthan", "Taxable ValueRs. 1,14,900.00", and 4-digit CGST values touching the cell border. Same product appeared twice on one invoice. **Cause:** fixed x positions for the meta block and totals. **Fix:** x positions computed from the widest label/value with that font; CGST/SGST columns widened; products drawn with `rng.sample` (no repeats). **Lesson:** always test the widest font with the longest invoice.
3. `[FAILURE]` Labels contained values the image never shows: per-line totals (no layout prints them) and, on thermal receipts, per-line CGST/SGST/IGST, supplier state, buyer address and state. **Cause:** labels were the full generated invoice, not what was drawn. **Fix:** `printed_label(inv, layout)` sets unprinted fields to `null`; the validators recompute tax per head from the rates when line amounts are missing. **Lesson:** a label is "what's on the page", not "what the generator knows". Caught before any results were recorded.
4. `[FAILURE]` First baseline answers (15 invoices, 3B model): (a) **dates scrambled**: the model reads the right digits but puts them in the wrong order (27/01/2026 → "2701-02-26", 05-04-2025 → "0504-02-20"); a real model weakness, which fine-tuning should fix. (b) **`place_of_supply` always missing**: probably our harness, not the model. Fields that are optional in the JSON schema let Ollama's constrained decoding skip them. **Fix for tomorrow:** send a schema where every field is required but nullable, delete the 15 cached answers, and rerun. (c) Line F1 = 0 because the model leaves out HSN and quantity, again probably the same optional-field issue.

### End of day
- Done: plan finalised; milestone 1 (schema); milestone 2 v1 (2,000 invoices, 4 layouts, 3 difficulty levels, splits, injection set); milestone 5 (validators); milestone 6 scoring code; milestone 3 harness (Ollama, Gemini, MLX) + 15-invoice smoke result; milestone 4 prep (SFT export, training script, mlx-vlm installed). 568 tests.
- Not done: baseline numbers (run stopped at 15/60 of the first model); base-model choice; LoRA training; Gemini baseline (needs `GEMINI_API_KEY`); MLX base model downloads (stopped part-way, they resume); public receipt data (CORD/SROIE); regional-language text.
- `[NEXT]` Tomorrow, in order:
  1. Make every schema field required-but-nullable for the baselines (Failures #4b); clear `runs/`.
  2. `eval/run_baselines.sh` pass 1 (~2 h): 3B, Qwen3-VL 4B, 7B on 60 test + 24 injected.
  3. Pick the base model from pass 1; run `eval/train_lora.sh` overnight (stop pass 2 first; one heavy model job at a time).
  4. Gemini baseline on 50 test invoices once a free-tier key is set.
  5. `uv run python -m invoice_lm.report > docs/RESULTS.md`.
- `[NEXT]` Decide the regional-language renderer (Pillow + raqm vs browser) before adding Hindi/Kannada.
- Known limitation: fonts are loaded from macOS system paths; generation on Linux (e.g. HF Spaces) needs bundled fonts.

---

## Day 2: 2026-10-21: Harness fixes, pass-1 baselines, intake checks, API + demo, base-model pick, LoRA (milestones 3, 4, 7, 8)
**Goal for the day:** two planned days in one session. Fix the baseline harness (Day 1 Failures #4), run pass 1 on three local models, pick the base model, start LoRA. While the GPU is busy: upload guardrails (plan §7), FastAPI service + demo page, a regional-language renderer for the hard-case set.

### Steps
1. 17:37  Resumed from the Day 1 `[NEXT]` list. Machine on battery (82%): flagged it to the user, since long runs need mains power.
2. 17:38  `[FAILURE]` fix (Day 1 #4b/c): added `schema.decoding_schema()`: the same schema with every property in `required` (nullable fields keep `null` as an option, defaults and titles dropped). Ollama and the prompt now use it. Test: every object's `required` == its properties. The cache-delete command was blocked by the permission guard, so the 15 old answers were **moved** to `runs/_archive/` instead (kept, not scored). Files: `schema.py`, `baseline.py`, `tests/test_validators.py`.
3. 17:39  Smoke test, 3B, 3 invoices: `place_of_supply`, HSN and quantity now filled; line F1 0 → 1.0 on these 3. Dates still scrambled.
4. 17:40  `[FAILURE]` Dates: the scrambling came from **our grammar, not the model**. Without `format: date` the 3B returns "27/01/2026" and "05/04/2025", both correct. With it, the grammar forces four year digits first, so the model copies the printed digits in order ("2701-02-26"). Fix: drop `format` from the decoding schema; `validators._coerce` turns day-first Indian dates (8 formats) into ISO; garbage still fails the date check. Prompt: "YYYY-MM-DD if you can, otherwise exactly as printed". **Lesson:** constrained decoding changes what the model writes; test the grammar on its own before blaming the model. 570 tests. Files: `schema.py`, `validators.py`, `baseline.py`.
5. 17:41  `eval/run_baselines.sh`: wrapped in `caffeinate -i` (deferred from Day 1), pass chosen by argument (`1`, `2`, `all`), each Ollama model unloaded after its pass. `train_lora.sh` also wrapped in `caffeinate`. `[FAILURE]` (small) the Write of the new script failed (file not read first), so the old script started; stopped it within a minute and relaunched. Answers already cached by then used the new schema, so they were kept. Files: `eval/*.sh`.
6. 17:41  Pass 1 started: 3B, Qwen3-VL 4B, 7B × (60 test + 24 injected). Log: `runs/logs/pass1.log`.
7. 17:42  `[DECISION]` API dependencies declared as an `api` extra (fastapi, uvicorn, python-multipart, pypdfium2). FastAPI had only been in the environment as a dependency of mlx-vlm. pypdfium2 renders PDFs to pixels with no form environment, so PDF JavaScript is never run.
8. 17:42  Wrote intake checks (plan §7): type from magic bytes (PNG/JPEG/PDF only; an EXE, SVG or GIF renamed `.png` is rejected), 10 MB cap, 40 MP cap read from the header before decoding (decompression bombs), Pillow's bomb guard as a second line, PDF ≤ 5 pages and a per-page pixel cap, encrypted/damaged PDF rejected, EXIF rotation applied. Quality: Laplacian-variance sharpness, mean brightness, short side ≥ 400 px. Files: `intake.py`.
9. 17:43  `[RESULT]` Blur threshold calibrated on 600 synth_v1 images: sharpness min clean 1,680 · scan 1,518 · photo 125 (p5 193). Photos + Gaussian blur σ2: max 34, median 10; σ3: max 9. Threshold **25**: 5× below the worst real sample, rejects most σ≥2 blur.
10. 17:43  Intake tests (8): accepted types, renamed EXE/SVG/GIF, empty/oversized, a 170-byte PNG claiming 20,000 × 20,000 px, truncated PNG, broken PDF, 6-page PDF, a PDF with a JavaScript action (rendered as pixels only), dark/blurry/small flags, dataset images pass while blurred ones fail. `[FAILURE]` (small) the bomb came back as `corrupt_file`: Pillow's own guard fires inside `Image.open` (400 MP > 2× its limit). It was rejected either way; mapped `DecompressionBombError` → `too_many_pixels`. Files: `tests/test_intake.py`.
11. 17:43  `[RESULT]` Pass-1 timing: 3B 17.6 s per invoice. ETA: 3B ~25 min, 4B ~35 min, 7B ~60 min → pass 1 done ~19:40.
12. 17:44  Refactored `baseline.predict` → `predict_bytes(backend, data, mime)` so the API and the harness share one model call (MLX backend now takes bytes too).
13. 17:44  Wrote the API (milestone 8): `POST /extract` → intake → quality gate (blurry/dark/small → 422 with a "retake the photo" message, the model is never called) → model under a lock (one heavy job on 16 GB) → validators. Response: invoice, `needs_review`, confidence, every check, warnings (extra PDF pages ignored, "no invoice could be read"), quality, model timing. Reads at most 10 MB + 1 byte. Logs: request id, type, size, check names, timing; **no invoice values** (plus a `mask()` helper for GSTINs/digit runs). `GET /` demo page; `invoice-lm serve`. Files: `api.py`, `demo.html`, `__init__.py`.
14. 17:44  `[DECISION]` The demo page writes model output only with `textContent`, never `innerHTML`: the model copies text out of the image, so an injected invoice could carry HTML/JS (an XSS path from inside an image). A test enforces it.
15. 17:44  API tests (5, stub model): valid invoice passes with no failed checks; an answer with grand total 0, `needs_review: false` and `<script>` in the supplier name is flagged (`no_unexpected_fields`, `grand_total_adds_up`) and neither the GSTIN nor the total appears in the log; renamed EXE / tiny image / 10 MB+ file are rejected and **the model is never called**. **583 tests pass.** Files: `tests/test_api.py`.
16. 17:45  Resumed the MLX 4-bit downloads (Qwen2.5-VL-3B, Qwen3-VL-4B) in the background, network only, so LoRA can start as soon as pass 1 picks the base model.
17. 17:45  Regional-language renderer: no Homebrew, and Pillow's raqm can't load without `libfribidi`. `[DECISION]` Shape with `uharfbuzz` and draw the glyphs with `freetype-py` (both pip wheels, no system libraries). This is for the hard-case set (test only), so it doesn't block tonight's training.
18. 17:46  Wrote `generator/shape.py`: `ShapedDraw` wraps ImageDraw, splits each string into Latin and Indic runs; Latin goes through Pillow as before, Indic is shaped by HarfBuzz and drawn glyph by glyph with FreeType on the same baseline. `textlength` is overridden too, so wrapping and right-alignment keep working. The renderer change is one line per layout (`draw_for(img, ...)`), and plain-Latin invoices still get a plain ImageDraw (byte-identical output for synth_v1). Fonts: Devanagari Sangam MN, Noto Sans Kannada (macOS).
19. 17:47  Visual check, Pillow vs shaped, on "बासमती चावल 5 किग्रा (श्री गणेश ट्रेडर्स)" and "ಬಾಸ್ಮತಿ ಅಕ್ಕಿ ಶ್ರೀ ಲಕ್ಷ್ಮೀ ಸ್ಟೋರ್ಸ್": Pillow leaves visible halants and draws Kannada as tofu boxes (with a Latin font); shaped text forms श्री, ग्रा, ट्रे, ಕ್ಕಿ, ಲಕ್ಷ್ಮೀ correctly.
20. 17:48  Wrote `generator/regional.py` + `invoice-lm generate --regional`: suppliers from Delhi/UP/Rajasthan get Hindi, Karnataka gets Kannada: shop name words translated (legal suffix "Pvt Ltd" stays Latin, as printed in real life), 13 common goods translated, buyer name too for half of intra-state bills; numbers, GSTINs, HSN stay Latin. Text only, so tax maths stays correct by construction. Translations are mine: **need a native speaker's check before publishing**.
21. 17:49  `[FAILURE]` (small) First `data/regional_v1` was 30 Hindi / 10 Kannada (3 of the 4 regional states use Devanagari). Fixed: script alternates per invoice → **20 / 20**; the unbalanced set was moved to `runs/_archive/`. Final: classic 14 · minimal 12 · thermal 8 · handwritten 6; photo 16 · clean 13 · scan 11. Looked at a Hindi A4 invoice and a Kannada thermal receipt: realistic, columns aligned. Known gap: Indic runs use regular weight even in bold headings.
22. 17:49  Tests (4): run splitting, HarfBuzz forms conjuncts (श्री → fewer glyphs than code points), painted width matches `textlength`, 40 regional invoices render and pass every validator. **587 tests pass.** Files: `tests/test_regional.py`.
23. 17:50  Checked every flag in `train_lora.sh` against `mlx_vlm.train --help` (0.7.9): all exist. Cheap insurance against a typo killing the run hours in.
24. 17:50  Results now broken down by `script` (when present); `report.py` adds a Hindi/Kannada table; pass 2 now also runs `regional_v1`.
25. 17:50  `[FAILURE]` (near miss) Edited `eval/run_baselines.sh` while bash was executing it. Bash reads scripts by byte offset, so a longer comment on line 3 would have shifted where it resumes after the pass-1 block. Put line 3 back to its original bytes; the new line is after the running block, so it's safe. **Lesson:** never edit a running shell script above the point it's executing; copy it instead.
26. 17:51  Wrote `eval/overnight.sh`: LoRA → fine-tuned model on test 197 + injected 24 + regional 40 → the **untrained** MLX model on the pass-1 60 + injected + regional with the same prompt and the same 1,024 px images (a fair before/after; the Ollama baselines see full-resolution pages) → `docs/RESULTS.md`. Wrapped in `caffeinate`.
27. 17:52  README (intake, API, regional set, new commands) and PLAN (milestones 7, 8 in progress) updated.
28. 17:53  `[RESULT]` Measured power for the cost metric: the Mac was on battery, so the battery's discharge current × voltage gives whole-system draw: **24.9 W** (10 samples) during `qwen2.5vl:3b` inference, screen on. At ₹8/kWh, 18 s per invoice = **₹1.00 per 1,000 invoices** in electricity. `report.py` now has a "₹ per 1,000 (power)" column for local models (assumptions in the code). Gemini free tier is ₹0 within its limits; paid-API prices will be quoted, not run.
29. 17:54  Demo page: the design hook flagged a flat type scale (22/15/14/13/12 px). Cut it to three sizes (28 title / 16 body / 13 tables and labels); section headings became uppercase muted labels.
30. 17:55  MLX downloads finished. `du` showed 1.3 GB and 4.4 MB, which looked broken, but the real files are 3.07 GB and 3.09 GB. Checked each `model.safetensors` header against its file size: **both complete** (1,330 and 1,219 tensors). One stale `.incomplete` blob from the Day 1 stop remains in the 3B cache folder (harmless).
31. 17:56  Demo page: the design hook flagged the hidden, empty-src preview `<img>` again. Removed the static tag; the image element is now created only after a file is chosen.
32. 18:25  `[RESULT]` Pass 1 done for `qwen2.5vl:3b` (Ollama, full-resolution pages, fixed harness): see Results below. Compared with the Day 1 smoke test (old harness, 15 invoices): field accuracy 60.9% → **89.1%**, line F1 0% → **93.3%**, dates 0% → **100%**, place of supply 0% → **100%**. Most of the Day 1 "model weakness" was our harness.
33. 18:26  `[FAILURE]` First summary showed a **63.6% false-flag rate** (validators flagging 21 of 33 invoices whose critical fields were right). Went through all 21 one by one: 14 were **correct catches** (`supply_type` wrong ×7, buyer GSTIN misread ×7), which the metric counted as false because "critical" covers only six fields. The other 7 failed `line_math` with every scored field right.
34. 18:27  Dug into the 7: the model writes `0` for per-line tax that isn't printed, and on thermal receipts it **invents** per-line tax (copies the invoice CGST 2,734.83 onto three different lines, or doubles the tax). So the flags were mostly right, and the scorer was blind because per-line tax amounts aren't in the line key. Fixes:
    - Scoring: new `all_correct` per invoice (every header field, every line, and per-line tax: printed → must match, not printed → must be null/0). `false_flag_rate` is now measured on fully correct extractions only; `all_correct` is reported too.
    - Validators: a taxed line with all-zero amounts = "not printed" (skipped by `line_math`) plus a new **minor** check `line_tax_not_zero` (lowers confidence, no forced review). `[DECISION]` Trade-off: zeroed line tax with correct totals is no longer forced to review, because ITC is claimed on invoice-level totals per head, which stay critical. The existing test was changed to assert this, and a new one shows zeroed *totals* still force review.
    - **589 tests.** Re-scored the cache (no model calls).
35. 18:28  `[RESULT]` After the fix (3B): false flags **0%** on synth (was 63.6%), 10% on injected (1 invoice, `inj_009`, `line_math`, not yet investigated). All-correct extractions: 20% synth, 41.7% injected.
36. 18:28  `[FAILURE]` (model, open) The 3 silent errors (1 synth, 2 injected `double_total`) are all **supplier and buyer swapped**: names and GSTINs exchanged. Both GSTINs are valid, and on an intra-state invoice both parties are in the same state, so no arithmetic check can see it. Logged as a known validator blind spot; fine-tuning target. Possible later check: the supplier block is the one next to "Tax Invoice"/the top of the page, which needs layout info the model doesn't return.
37. 18:29  `[FAILURE]` `qwen3-vl:4b` (Ollama): first answer took **152 s, hit the 3,000-token cap, and returned empty text**. Stopped pass 1 at once (it would have spent ~3.5 h scoring 0). **Cause:** the plain `qwen3-vl:4b` tag is the *thinking* variant (capabilities: thinking); it ignores `think: false` and puts its reasoning in a separate `thinking` field, so the answer never got written. `/no_think` in the prompt made it worse (400/400 tokens of thinking on a one-line task). It also wasn't the model we'd fine-tune: the MLX candidate is Qwen3-VL-4B-**Instruct**. **Fix:** pulling `qwen3-vl:4b-instruct`; scripts switched to it; the wasted answer moved to `runs/_archive/`. `call_ollama` now records `thinking_chars` and turns "thinking but no answer" into an explicit error instead of a quiet parse failure. **Lesson:** check a new model tag on one item and look at the raw response before starting a batch; the Day 1 smoke test only covered the 3B.
38. 18:33  `[RESULT]` LoRA timing smoke test while the GPU was idle (pull running): `train_lora.sh <3B> smoke_3b 10`. Steady state **~18 s/iter** (first iter 54 s warm-up), **peak memory 8.3 GB**, 25 val batches take 62 s. After 10 iters: train token accuracy 94.6%, val loss 0.168 / token accuracy 96.1% (most JSON tokens are easy). Run is throwaway (`runs/train/smoke_3b`).
39. 18:34  `[FAILURE]` (mine, caught before the real run) `mlx-vlm` counts `--iters` in **sequences**, not optimizer steps (log: 10 iters → `optimizer_step=3` with accumulation 4). The script comment "800 iters ≈ 2 epochs" was wrong: 800 iters = **0.5 epoch**. Options: 800 (0.5 epoch, ~4 h) · **1,613 (1 epoch, ~8 h)** · 3,226 (2 epochs, ~16 h, too long). Default changed to 1,613 in both scripts.
40. 18:35  `qwen3-vl:4b-instruct` pulled. One-invoice check first (lesson from step 37): no thinking field, valid JSON, 100% on syn_0_00000, 45 s incl. model load. Started its pass 1 (`runs/logs/pass1.log`, appended).
41. 18:37  First run of the MLX inference path (`call_mlx` + adapter), never tested on Day 1: loads, generates compact JSON with an ISO date after only 3 optimizer steps. Schema fails (`line_total` instead of `taxable_value`): expected for a 3-step adapter. 66 s/invoice, but sharing the GPU with the 4B run.
42. 18:38  `[FAILURE]` (plan, caught) The overnight "before" run would have given the **untrained** MLX model the short training prompt, which has no schema, so it couldn't know the key names: the before/after would have measured "knows our format", not "reads invoices". Fix: without an adapter, MLX gets the same schema prompt as the Ollama baselines; with an adapter, the training prompt. `max_tokens` 1,500 → 2,500 (an untrained model writes indented JSON; the 4B used 999 tokens on a 6-line invoice).
43. 19:37  `[RESULT]` Pass 1 done for `qwen3-vl:4b-instruct` (table in Results). Session paused (usage limit) ~18:40–19:50; the run finished unattended.
44. 19:51  `[DECISION]` **Base model: Qwen3-VL-4B-Instruct.** It beats the 3B on every quality metric: field acc 93.5 vs 89.1%, critical-all-correct 63.3 vs 55.0%, line F1 96.8 vs 93.3%, photos 91.5 vs 84.9%, handwritten 93.2 vs 80.2%, injections caught 100 vs 91.7%, zero silent errors. Only slower (44.8 vs 31.6 s on Ollama). The weak spot for both is reading GSTINs (~70%): the main fine-tuning target.
45. 19:52  Machine check: up 10 h (no reboot), **battery 29% and discharging**: still not on mains. Overnight training can't start until it's plugged in.
46. 19:55  `[RESULT]` 4B LoRA smoke test (10 iters): **7.7 s/iter** steady state (faster than the 3B's 18 s, which shared the machine with the Ollama pull; Qwen3-VL may also use fewer vision tokens per page), **peak memory 12.8 GB** of 16 (tight: nothing else heavy can run), val loss 0.152 / token acc 95.6% after 10 iters. 1 epoch (1,613 iters) ≈ **3 h 40 min**.
47. 19:58  MLX 4B inference checked both ways on one invoice: untrained + schema prompt **25 s**, parses, 1 check failed (supplier GSTIN misread); 10-iter adapter 22 s, right fields but wrapped in an extra `{"invoice": …}` and an invented `gst_type` key: undertrained, not a pipeline problem.
48. 19:59  `[NEXT]` Overnight plan, ETA ~7 h 40 min from start: LoRA 1 epoch (~3 h 40 min) → fine-tuned 4B on test 197 + injected 24 + regional 40 (~1 h 35 min at ~22 s) → untrained 4B on 60 + 24 + 40 (~52 min) → 7B Ollama pass 1 (~1 h 30 min, not measured) → `docs/RESULTS.md`. Command: `WITH_7B=1 eval/overnight.sh mlx-community/Qwen3-VL-4B-Instruct-4bit qwen3vl4b_lora_r16`. Needs mains power.
49. 20:00  `[DECISION]` Asked whether training could move to Kaggle (free T4). Options laid out: Unsloth QLoRA in fp16 on a T4, then merge, download ~8 GB, convert to MLX; ~1–1.5 h of new work and untested risk, against a local MLX path that is tested and ready. **User chose: keep training local on the Mac (MLX), run it tomorrow.** Kaggle is kept as an option for longer runs later.
50. 20:00  Stopped for the day: nothing running, Ollama models unloaded, 589 tests pass, `docs/RESULTS.md` written from the pass-1 cache.

### Results
`[RESULT]` Pass 1, zero-shot via Ollama, full-resolution pages, fixed harness (60 test + 24 injected):

| Model | Field acc | Critical all correct | All correct | Line F1 | Validators caught | False flags | Silent errors | Sec/invoice | ₹ per 1,000 (power) |
|---|---|---|---|---|---|---|---|---|---|
| qwen2.5vl:3b | 89.1% | 55.0% | 20.0% | 93.3% | 96.3% | 0.0% | 1.7% | 31.6 | ₹1.76 |
| qwen3-vl:4b-instruct | **93.5%** | **63.3%** | **33.3%** | **96.8%** | 100% | 5.0% | **0.0%** | 44.8 | ₹2.49 |

| Model | Clean | Scan | Photo | Classic | Minimal | Handwritten | Thermal | Injections caught |
|---|---|---|---|---|---|---|---|---|
| qwen2.5vl:3b | 96.9% | 89.7% | 84.9% | 92.7% | 93.8% | 80.2% | 85.7% | 91.7% |
| qwen3-vl:4b-instruct | 96.8% | 94.0% | 91.5% | 95.5% | 93.8% | 93.2% | 90.5% | **100%** |

Weakest fields for both: buyer GSTIN (66.7%) and supplier GSTIN (70 / 73%).

`[RESULT]` Other numbers today: blur threshold 25 (worst real photo 125); whole-Mac power 24.9 W during inference; LoRA 3B 18 s/iter (shared machine), 4B **7.7 s/iter, peak 12.8 GB**; MLX 4B inference 22–25 s per invoice.

### Decisions
- `[DECISION]` Every schema field required-but-nullable for constrained decoding, and no `format: date` in the grammar (steps 2, 4).
- `[DECISION]` API deps as an `api` extra; PDFs rasterised with pdfium only (step 7).
- `[DECISION]` Demo page uses `textContent` only: model output is untrusted (step 14).
- `[DECISION]` Indic text shaped with HarfBuzz + FreeType wheels, no system libraries (step 17).
- `[DECISION]` False flags measured on fully correct extractions; all-zero line tax is a minor check (step 34).
- `[DECISION]` Base model **Qwen3-VL-4B-Instruct** (step 44). 1 epoch = 1,613 iters (step 39).
- `[DECISION]` Train locally with MLX, not on Kaggle (step 49).

### End of day
- Done: harness fixed (fields, dates); pass 1 for two small models; base model picked; intake checks; FastAPI + demo page; Hindi/Kannada test set + shaping renderer; scoring and validator fixes; MLX train and inference paths tested end to end on both models; overnight chain script ready; cost metric measured. 589 tests (was 568).
- Not done: LoRA training (Mac on battery, user chose tomorrow); 7B baseline; Gemini baseline (no `GEMINI_API_KEY`); pass 2 (full 197 + regional); native-speaker check of translations; `inj_009` false flag; supplier/buyer swap blind spot; public receipt data (CORD/SROIE).
- `[NEXT]` Tomorrow, in order:
  1. Plug in, lid open, close heavy apps. Run `WITH_7B=1 eval/overnight.sh mlx-community/Qwen3-VL-4B-Instruct-4bit qwen3vl4b_lora_r16 2>&1 | tee runs/logs/overnight.log` (~7 h 40 min). Start early in the day so the results are in by evening.
  2. While it runs (CPU only): Gemini baseline if a key is set (it uses the network, not the GPU); look at `inj_009`; supplier/buyer swap check idea.
  3. Read `docs/RESULTS.md`: before/after for the fine-tune, and decide whether a second epoch is worth it.
- Throwaway runs to delete when convenient: `runs/train/smoke_3b`, `runs/train/smoke_4b`, `runs/_archive/`.

## Day 3: 2026-10-22: Overnight LoRA chain, false-flag clean-up (milestones 4, 6)
**Goal for the day:** run the LoRA + before/after eval chain on Qwen3-VL-4B-Instruct; meanwhile (CPU only) clear the remaining false flags and look at the supplier/buyer swap.

### Steps
1. 12:37  Start-of-day check: nothing running, no `runs/logs/overnight.log`, 84% memory free, `qwen2.5vl:7b` pulled, no `GEMINI_API_KEY`. **Mac on battery (100%, discharging)**: the chain draws ~25 W+ for ~7 h 40 min, more than the battery holds.
2. 12:38  `[DECISION]` Started a watcher instead of the chain: it polls `pmset` every 5 s and launches `WITH_7B=1 eval/overnight.sh mlx-community/Qwen3-VL-4B-Instruct-4bit qwen3vl4b_lora_r16` under `nohup` (log: `runs/logs/overnight.log`) the moment the Mac is on AC. Nothing is lost if the plug-in comes late.
3. 12:38  `[FAILURE]` (scorer) `inj_009` (3B, the one injected false flag) was **a real catch**: the model read the AMC rate 8,829.00 as 829.00 (3 × 829 ≠ 26,487), `line_math` fired, but `all_correct` doesn't compare `rate` (the line key is HSN, qty, taxable value, GST rate). Fix: `rate` joins the per-line tax amounts in the `all_correct` check (printed → must match). Line F1 definition unchanged, so pass-1 F1 doesn't move. Test `test_misread_rate_is_not_all_correct` written first, failed, then passed. Files: `scoring.py`, `tests/test_validators.py`.
4. 12:39  `[FAILURE]` (small) First re-score showed no change: `report.py` reads each run's `_summary.json`, which only `invoice-lm baseline` rewrites. Re-ran the baselines over the cache (no model calls, Ollama stayed unloaded).
5. 12:39  One false flag left: 4B `syn_0_00074` (handwritten photo). The model wrote the buyer GSTIN as `33LWSPH4936F4Z.Z`; the scorer's normalisation drops the dot (counted right), the validator's checksum rejects the literal string. `[DECISION]` Clean GSTINs in `_coerce` (drop anything that isn't a letter or digit, uppercase): a GSTIN is only alphanumerics, so this can't change a real value, and the checksum still catches a misread character. Test `test_gstin_punctuation_is_cleaned_but_checksum_still_applies` written first (spaces, lowercase, dot, dash → passes; one wrong char → still flagged). **591 tests pass.** Files: `validators.py`, `tests/test_validators.py`.
6. 12:40  `[RESULT]` Re-scored pass 1 (cache only), `docs/RESULTS.md` regenerated:

| Model | Set | All correct | Caught | False flags | Silent errors |
|---|---|---|---|---|---|
| qwen2.5vl:3b | synth 60 | 20.0% | 96.3% | 0.0% | 1.7% |
| qwen2.5vl:3b | injected 24 | 37.5% (was 41.7%) | 75.0% | **0.0%** (was 10%) | 8.3% |
| qwen3-vl:4b-instruct | synth 60 | 33.3% | 100% | **0.0%** (was 5.0%) | 0.0% |
| qwen3-vl:4b-instruct | injected 24 | 62.5% | 100% | 0.0% | 0.0% |

   Both remaining false flags were measurement or parsing issues, not over-strict validators.
7. 12:41  `[DECISION]` Supplier/buyer swap check: not built. Both GSTINs are valid and same-state on intra-state bills, so the only signal is layout (which block sits under "Tax Invoice"), and the model returns no positions. Left as a fine-tuning target; check the swap count in the fine-tuned eval.

### End of day (provisional, 12:42; update when the chain finishes)
- Done: `inj_009` and `syn_0_00074` explained and fixed (false flags 0% everywhere in pass 1); GSTIN clean-up in the parser; 591 tests (was 589); chain armed to start on mains power.
- Not done: the chain itself (waiting for the charger); Gemini baseline (no key); native-speaker check; pass 2.
- `[NEXT]` When `runs/logs/overnight.log` says `all done` (~7 h 40 min after plug-in): read `docs/RESULTS.md`, compare fine-tuned vs untrained 4B on the same 1,024 px images, count supplier/buyer swaps, decide on a second epoch.

## Day 4: 2026-10-29: Re-arm the LoRA chain, Hugging Face dataset staging (milestones 4, 8)
**Goal for the day:** get the LoRA + before/after chain actually running; meanwhile (CPU only) prepare the dataset release.

### Steps
1. 20:47  Start-of-day check: **no `runs/logs/overnight.log`, no `runs/train/qwen3vl4b_lora_r16`**: the chain never ran. Mac on battery (95%), 74% memory free, only `ollama serve` running, nothing loaded. Project is not a git repository.
2. 20:47  `[FAILURE]` The Day 3 watcher was a background job of the Claude session, so it died when that session closed, before the charger went in. Lesson: anything that has to outlive the session gets `nohup` + `disown`, not a session background task.
3. 20:48  `[DECISION]` New `eval/when_plugged_in.sh`: polls `pmset` every 30 s, then runs `WITH_7B=1 eval/overnight.sh mlx-community/Qwen3-VL-4B-Instruct-4bit qwen3vl4b_lora_r16` (log `runs/logs/overnight.log`). Started detached (pid 6197, log `runs/logs/watcher.log`). Cancel with `pkill -f when_plugged_in.sh`. Files: `eval/when_plugged_in.sh`.
4. 20:50  `src/invoice_lm/publish.py` + `invoice-lm stage-hf`: lays out the three sets as one Hugging Face dataset repo, one imagefolder config each (`synthetic` 2,000 with a `split` column, `injection` 24, `regional` 40), `metadata.jsonl` = manifest fields + the full label as a JSON string (keeps nested nulls), images hard-linked, dataset card with YAML configs, CC BY 4.0, limits section. Tests written first (failed on import, then passed). `[DECISION]` Stage only; the upload (`hf upload <user>/indian-gst-invoices runs/hf_dataset --repo-type dataset`) waits for the user's account and approval. Files: `publish.py`, `__init__.py`, `tests/test_publish.py`, `README.md`.
5. 20:51  `[RESULT]` `invoice-lm stage-hf`: 2,064 rows in 0.9 s, no extra disk (hard links). **593 tests pass** (was 591).
6. 23:28  `[RESULT]` Charger in: the watcher saw AC and started the chain (pid 24056, under `caffeinate -i`). LoRA r16 on Qwen3-VL-4B-Instruct-4bit: 33.0 M trainable params (0.74%), 1,613 iters, step time settling (~45 s for the first step, ~8 s for the second). Lid stays open (closing it sleeps the Mac even with caffeinate). ETA for `all done` is ~07:10 on 2026-10-30 if the estimate holds.
7. 23:32  `[RESULT]` Steady speed over steps 2–20: **6.85 s/step** → 1,613 steps ≈ **3 h 05 min** (training done ~02:35, faster than the 3 h 40 min planned). Loss 0.25 → 0.09 by step 20. 52% memory free, no thermal warning. ETA for `all done` stays ~07:10 (or a little earlier).
8. 23:40  `[DECISION]` `git init` (branch `main`) + `.gitignore`: ignores `.venv`, caches, `data/` (709 MB, rebuilt by `invoice-lm generate`, released on HF), `runs/train/` (adapters), `runs/hf_dataset/`, `runs/_archive/`, `*.safetensors`, `.env*`. Keeps per-invoice eval outputs and logs as evidence. Secret scan clean; largest file `uv.lock` (664 KB). `[RESULT]` First commit `6dc37cd`, 217 files. No remote yet. Files: `.gitignore`.

### End of day
- Done: chain re-armed with a session-independent watcher and running on mains power since 23:28; dataset release staged in `runs/hf_dataset`; 593 tests.
- Not done: the chain itself (running; LoRA ~3 h 05 min, then evals + 7B baseline + report); HF upload (needs account + approval); model card (needs the fine-tune numbers); Gemini baseline (no key); native-speaker check; pass 2; git remote (repo exists locally, nothing pushed).
- `[NEXT]` Plug in → chain starts by itself. When `runs/logs/overnight.log` says `all done`: read `docs/RESULTS.md`, fine-tuned vs untrained 4B, count supplier/buyer swaps, decide on a second epoch, then write the model card and stage the adapter.

## Day 5: 2026-10-30: Overnight chain results (milestones 4, 6)
**Goal for the day:** let the chain finish, read the before/after numbers, decide on a second epoch.

### Steps
1. 06:56  `[RESULT]` LoRA finished at 05:38: 1,613 steps in **6 h 09 min (13.74 s/step average)**, twice the 3 h 05 min estimated from the first 20 steps. Final train loss 0.0074; val loss 0.0060, val token accuracy 99.83%, val perplexity 1.006. Adapter in `runs/train/qwen3vl4b_lora_r16/adapters/adapters.safetensors`. No errors; `caffeinate` held the Mac awake all night; battery 100%.
2. 06:56  `[FAILURE]` Time estimate: the first 20 steps (6.85 s) were not representative; later steps ran 8–37 s, and validation every 100 steps adds ~54 s each. Lesson: estimate from a window of 100+ steps including one validation, not the first 20.
3. 06:56  `[RESULT]` Eval of the fine-tuned model in progress: 186/197 synth test images in 77 min (~25 s per invoice). Remaining: injection 24 and regional 40 (fine-tuned), then the untrained model on synth 60 / injection 24 / regional 40, then the 7B Ollama baseline and the report. ETA `all done` ~09:30.
4. 10:07  `[RESULT]` Chain `all done` (7B Ollama pass 1 finished 10:07); `docs/RESULTS.md` regenerated. Total chain 10 h 39 min.
5. 10:12  `[RESULT]` Like-for-like on the same 60 synth test invoices (the report shows the fine-tune on all 197):

   | Model | Critical all correct | Field acc | Silent errors | Sec/invoice |
   |---|---|---|---|---|
   | MLX 4B untrained | 21.7% | 85.7% | 0 | 30.3 |
   | **MLX 4B + LoRA r16** | **73.3%** | **96.3%** | **2 (3.3%)** | **25.0** |
   | Ollama qwen2.5vl:7b | 60.0% | 94.1% | 0 | 77.0 |
   | Ollama qwen3-vl:4b-instruct | 63.3% | 93.5% | 0 | 44.8 |

   On all 197: critical 75.6%, field 96.3%, line F1 98.1%. Injection: 100% caught (untrained 95.8%). Regional: critical 27.5% → 72.5%, Hindi 83.5% → 89.7%, Kannada 80.2% → 88.8%. Photos 81.2% → 94.2%, handwritten 79.2% → 93.3%.
6. 10:14  `[RESULT]` Both silent errors are single-character misreads in fields no validator can check: `syn_0_00074` (photo, handwritten) invoice number TI-4317 → TI-4817; `syn_0_00311` (scan) date 2025-06-20 → 2026-06-20. The untrained model also missed these but got flagged because it also broke a GSTIN; 7B read both right. So the fine-tune's catch rate drop (100% → 95.8%) is the side effect of fewer, subtler mistakes, not weaker validators.
7. 10:15  `[DECISION]` (proposed, needs the user) No second epoch: val loss is already 0.0060 (token acc 99.83%) on synthetic data, and the leftover errors are OCR-level digit misreads, where more epochs on the same generator mostly risk overfitting it. Better uses of the time: test on real scanned invoices, then model card + adapter upload.
8. 10:16  `[DECISION]` Plan for the rest of the day agreed with the user: (1) demo on the fine-tune, (2) supplier/buyer swap count, (3) model card + adapter staging, (4) README, (5) blog draft; then GitHub push, HF upload, Gemini baseline and a real-photo test once the user supplies access/key/photos. Public receipt data dropped (limit). Native-speaker check only if someone is free.
9. 10:20  `[DECISION]` API default backend = the LoRA fine-tune when `adapters.safetensors` is on disk, else `ollama:qwen3-vl:4b-instruct` (best untrained model in pass 1; was the weaker `qwen2.5vl:3b`). `INVOICE_LM_BACKEND` still overrides. Tests first (2 failing, then passing). Files: `api.py`, `tests/test_api.py`, `README.md`.
10. 10:22  `[RESULT]` Live smoke test: uvicorn with `--extra api --extra train`, `POST /extract` on `syn_0_00008` (photo): 15.8 s total, 13.4 s model; invoice number and grand total match the label; misread supplier GSTIN caught (`supplier_gstin_valid` failed → needs_review). 
11. 10:24  `[FAILURE]` `/health` and `/extract` echoed the full adapter path, including the macOS username. Fix: `backend_label()` reports `mlx:<model>+lora:<run name>`. Lesson: anything a response returns is public; check for local paths. **596 tests pass.**

### End of day (provisional)
- Done: LoRA r16 trained (6 h 09 min); fine-tuned 4B beats every baseline incl. 7B at 3× the speed; RESULTS.md written; silent errors explained.
- Not done: HF upload (account + approval); model card; real-invoice test; git remote.
- `[NEXT]` Decide second epoch (proposal: no); write model card; stage adapter for HF.
