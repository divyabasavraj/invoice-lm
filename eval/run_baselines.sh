#!/usr/bin/env bash
# Zero-shot baselines. Pass 1: 60 test invoices + 24 injected per model (quick numbers).
# Pass 2: the full 197-invoice test split (reuses the cache from pass 1).
# Usage: eval/run_baselines.sh [1|2|all]   (default 1). Keeps the Mac awake while running.
set -u
[ -z "${CAFFEINATED:-}" ] && CAFFEINATED=1 exec caffeinate -i "$0" "$@"
PASS=${1:-1}
MODELS=${MODELS:-"ollama:qwen2.5vl:3b ollama:qwen3-vl:4b-instruct ollama:qwen2.5vl:7b"}
if [ "$PASS" = 1 ] || [ "$PASS" = all ]; then
  for m in $MODELS; do
    uv run invoice-lm baseline "$m" --data data/synth_v1 --limit 60 > /dev/null
    uv run invoice-lm baseline "$m" --data data/injection_v1 > /dev/null
    echo "$(date +%H:%M) pass1 done $m"
    ollama stop "${m#ollama:}" 2>/dev/null || true
  done
fi
if [ "$PASS" = 2 ] || [ "$PASS" = all ]; then
  for m in $MODELS; do
    uv run invoice-lm baseline "$m" --data data/synth_v1 > /dev/null
    uv run invoice-lm baseline "$m" --data data/regional_v1 > /dev/null  # 40 Hindi/Kannada
    echo "$(date +%H:%M) pass2 done $m"
    ollama stop "${m#ollama:}" 2>/dev/null || true
  done
fi
