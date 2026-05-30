#!/bin/bash
set -euo pipefail

# Railway cron runner for HVTracker.
# Runs as a one-shot job, then exits. Railway starts it on the cron schedule.

echo "=== HVTracker cron run: $(date -u '+%Y-%m-%d %H:%M UTC') ==="

# Clone fresh copy (shallow, fast)
git clone --depth 1 "https://x-access-token:${GITHUB_TOKEN}@github.com/YugantM/hvtracker.git" /tmp/hvtracker
cd /tmp/hvtracker

# Copy cached data from the image (history snapshots, scorecard cache)
# but prefer the repo's versions since they're more recent
cp -n /app/scorecard-cache.json . 2>/dev/null || true

MODE="${CRON_MODE:-batch}"
ARGS=()

case "$MODE" in
  batch)
    HOUR=$(date -u +%-H)
    BATCH_NUM=$(( (HOUR / 4) + 1 ))
    [ "$BATCH_NUM" -gt 6 ] && BATCH_NUM=6
    ARGS=(--batch "$BATCH_NUM/6")
    echo "=== Refreshing batch $BATCH_NUM/6 (hour=$HOUR UTC) ==="
    ;;
  full)
    echo "=== Running full refresh ==="
    ;;
  pending)
    ARGS=(--pending-only)
    echo "=== Refreshing pending agents only ==="
    ;;
  render)
    ARGS=(--render-only)
    echo "=== Rendering from cached state only ==="
    ;;
  *)
    echo "Unknown CRON_MODE: $MODE" >&2
    exit 2
    ;;
esac

python3 fetch_and_build.py "${ARGS[@]}"

echo "=== Build complete, pushing ==="
git config user.name "hvtracker-bot"
git config user.email "hvtracker-bot@users.noreply.github.com"

git add -A
if git diff --cached --quiet; then
  echo "No changes — skipping commit."
else
  git commit -m "chore: regenerate leaderboard $(date -u '+%Y-%m-%d %H:%M') ${ARGS[*]:-[railway]}"
  pushed=0
  for i in 1 2 3; do
    if git push; then
      pushed=1
      break
    fi
    echo "Push failed (attempt $i/3), rebasing..."
    git pull --rebase origin main
  done
  if [ "$pushed" -ne 1 ]; then
    echo "Push failed after 3 attempts." >&2
    exit 1
  fi
fi

echo "=== Done: $(date -u '+%Y-%m-%d %H:%M UTC') ==="
