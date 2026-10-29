#!/usr/bin/env bash
# LoRA fine-tune on the M5 (16 GB). Run alone: no Ollama model loaded at the same time.
# Usage: eval/train_lora.sh <hf-model> <run-name> [iters]
set -euo pipefail
[ -z "${CAFFEINATED:-}" ] && CAFFEINATED=1 exec caffeinate -i "$0" "$@"
MODEL=${1:-mlx-community/Qwen2.5-VL-3B-Instruct-4bit}
NAME=${2:-qwen25vl3b_lora_r16}
ITERS=${3:-1613}
OUT=runs/train/$NAME
mkdir -p "$OUT"
ollama stop qwen2.5vl:7b qwen2.5vl:3b qwen3-vl:4b-instruct 2>/dev/null || true
uv run invoice-lm export-sft --data data/synth_v1
# mlx-vlm counts --iters in sequences (10 iters = 3 optimizer steps with accumulation 4),
# so 1,613 iters = 1 epoch = ~403 optimizer steps. Measured 2026-10-21: ~18 s/iter on the 3B
# (peak 8.3 GB), so 1 epoch is ~8 h.
uv run --extra train python -m mlx_vlm.train \
  --model "$MODEL" --data data/synth_v1/sft \
  --train-type lora --lora-rank 16 --lora-alpha 32 --lora-dropout 0.05 \
  --learning-rate 1e-4 --batch-size 1 --gradient-accumulation-steps 4 --iters "$ITERS" \
  --max-seq-length 3072 --grad-checkpoint --train-on-completions \
  --steps-per-report 10 --steps-per-eval 100 --val-batches 25 --steps-per-save 100 \
  --output-path "$OUT/adapters" 2>&1 | tee "$OUT/train.log"
