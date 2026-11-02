#!/bin/zsh
# 一条流水线：逐块板调用 codex exec，跳过已有 round-report.md 的板子，每块结束提交一次。
#   evals/boards/_tools/run_lane.sh lane-1 [--model gpt-6.1-sol] [--effort high] [--max N]
# 在 SR 工作树根目录运行；日志在 $LOGDIR（默认 ~/.cache/sr-boards/_logs/<lane>/）。
set -u
LANE=${1:?lane name, e.g. lane-1}; shift
MODEL=gpt-6.1-sol; EFFORT=high; MAX=1000
while [ $# -gt 0 ]; do case "$1" in
  --model) MODEL=$2; shift 2;; --effort) EFFORT=$2; shift 2;; --max) MAX=$2; shift 2;; *) echo "unknown $1"; exit 2;; esac; done
ROOT=$(git rev-parse --show-toplevel) || exit 1
cd "$ROOT"
LOGDIR=${LOGDIR:-$HOME/.cache/sr-boards/_logs/$LANE}; mkdir -p "$LOGDIR" "evals/boards/_lanes/$LANE"
TEMPLATE=evals/boards/_tools/board-prompt.md
BOARDS=$(python3 -c "import json,sys; print('\n'.join(json.load(open('evals/boards/_lanes/$LANE.json'))['boards']))") || exit 1
done=0
for B in ${(f)BOARDS}; do
  [ $done -ge $MAX ] && break
  if [ -s "evals/boards/$B/round-report.md" ]; then continue; fi
  mkdir -p "evals/boards/$B"
  PROMPT=$(sed -e "s/{{BOARD_ID}}/$B/g" -e "s/{{LANE}}/$LANE/g" "$TEMPLATE")
  echo "[$(date '+%H:%M')] $LANE: $B start" | tee -a "$LOGDIR/_lane.log"
  codex exec -C "$ROOT" -m "$MODEL" -c model_reasoning_effort="\"$EFFORT\"" -s workspace-write \
    --add-dir "$HOME/.cache/sr-boards" --color never -o "$LOGDIR/$B.last.md" "$PROMPT" < /dev/null > "$LOGDIR/$B.log" 2>&1
  rc=$?
  if [ ! -s "evals/boards/$B/round-report.md" ]; then
    printf '# %s\n\n流水线 %s：codex exec 退出码 %s，没有产出报告；见日志 %s\n' "$B" "$LANE" "$rc" "$LOGDIR/$B.log" > "evals/boards/$B/round-report.md"
  fi
  git add "evals/boards/$B" "evals/boards/_lanes/$LANE" 2>/dev/null
  git -c user.name="sr-boards $LANE" -c user.email="sr-boards@local" commit -q -m "boards/$B: SR review and attribution ($LANE, codex rc=$rc)" || true
  echo "[$(date '+%H:%M')] $LANE: $B done rc=$rc" | tee -a "$LOGDIR/_lane.log"
  done=$((done+1))
done
echo "[$(date '+%H:%M')] $LANE: finished ($done boards this run)" | tee -a "$LOGDIR/_lane.log"
