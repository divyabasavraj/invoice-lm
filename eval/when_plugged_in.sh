#!/usr/bin/env bash
# Wait for mains power, then run the overnight chain. Detached with nohup, so it survives the
# terminal (and the Claude session) closing; a session-bound watcher died this way on 2026-10-22.
# Usage: nohup eval/when_plugged_in.sh > runs/logs/watcher.log 2>&1 &
# Cancel: pkill -f when_plugged_in.sh
cd "$(dirname "$0")/.." || exit 1
mkdir -p runs/logs
echo "$(date '+%F %H:%M') waiting for AC power (pid $$)"
until pmset -g batt | grep -q "AC Power"; do sleep 30; done
echo "$(date '+%F %H:%M') on AC, starting chain"
WITH_7B=1 eval/overnight.sh mlx-community/Qwen3-VL-4B-Instruct-4bit qwen3vl4b_lora_r16 \
  > runs/logs/overnight.log 2>&1
echo "$(date '+%F %H:%M') chain exited ($?)"
