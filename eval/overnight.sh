#!/usr/bin/env bash
# Overnight chain: LoRA fine-tune, then score the untrained and fine-tuned MLX model on the
# same images at the same 1,024 px (a clean before/after), then write docs/RESULTS.md.
# Usage: [WITH_7B=1] eval/overnight.sh <hf-model> <run-name> [iters]
set -uo pipefail
[ -z "${CAFFEINATED:-}" ] && CAFFEINATED=1 exec caffeinate -i "$0" "$@"
MODEL=${1:-mlx-community/Qwen2.5-VL-3B-Instruct-4bit}
NAME=${2:-qwen25vl3b_lora_r16}
ITERS=${3:-1613}
ADAPTER=runs/train/$NAME/adapters
echo "$(date +%H:%M) train start $NAME"
eval/train_lora.sh "$MODEL" "$NAME" "$ITERS" || { echo "$(date +%H:%M) TRAIN FAILED"; exit 1; }
echo "$(date +%H:%M) train done"
for spec in "mlx:$MODEL+$ADAPTER" "mlx:$MODEL"; do
  for ds in synth_v1 injection_v1 regional_v1; do
    LIMIT=""
    [ "$spec" = "mlx:$MODEL" ] && [ "$ds" = synth_v1 ] && LIMIT="--limit 60"  # zero-shot: pass-1 size
    uv run --extra train invoice-lm baseline "$spec" --data "data/$ds" $LIMIT > /dev/null
    echo "$(date +%H:%M) eval done $spec $ds"
  done
done
# The 7B Ollama baseline waits until training is done (one heavy model job at a time).
[ -n "${WITH_7B:-}" ] && MODELS="ollama:qwen2.5vl:7b" eval/run_baselines.sh 1
uv run python -m invoice_lm.report > docs/RESULTS.md
echo "$(date +%H:%M) all done"
