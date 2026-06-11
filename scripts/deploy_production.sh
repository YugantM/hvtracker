#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${RAILWAY_PROJECT_ID:-336fa70c-21a7-4524-984b-b6035ea42773}"
ENVIRONMENT="${RAILWAY_ENVIRONMENT:-production}"
SERVICE="${RAILWAY_SERVICE:-web}"
MODE="source"
SKIP_CHECKS=0

usage() {
  cat <<'EOF'
Manual production deploy helper for HVTracker.

Usage:
  scripts/deploy_production.sh [--source|--local] [--skip-checks]

Modes:
  --source      Redeploy the latest configured source on Railway (default).
                Use this after pushing/merging to GitHub main.
  --local       Upload and deploy the current local workspace to Railway.
                Use this for an emergency/manual deploy from your machine.

Options:
  --skip-checks Skip the local pytest/render-only verification step.

Overrides:
  RAILWAY_PROJECT_ID   Railway project id
  RAILWAY_ENVIRONMENT  Railway environment name
  RAILWAY_SERVICE      Railway service name
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --source)
      MODE="source"
      shift
      ;;
    --local)
      MODE="local"
      shift
      ;;
    --skip-checks)
      SKIP_CHECKS=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

command -v railway >/dev/null || { echo "railway CLI not found" >&2; exit 1; }
command -v jq >/dev/null || { echo "jq not found" >&2; exit 1; }

echo "==> Railway target"
echo "project=$PROJECT_ID environment=$ENVIRONMENT service=$SERVICE mode=$MODE"

if [[ "$SKIP_CHECKS" -ne 1 ]]; then
  echo "==> Running local verification"
  pytest -q tests/test_render_sync.py tests/test_helpers.py
  python3 fetch_and_build.py --render-only >/tmp/hvtracker-render-check.log
  tail -n 5 /tmp/hvtracker-render-check.log
fi

if [[ "$MODE" == "source" ]]; then
  echo "==> Triggering Railway source redeploy"
  railway redeploy \
    --project "$PROJECT_ID" \
    --environment "$ENVIRONMENT" \
    --service "$SERVICE" \
    --from-source \
    --yes \
    --json
else
  echo "==> Uploading local workspace to Railway"
  railway up \
    --detach \
    -m "manual deploy: $(date -u '+%Y-%m-%d %H:%M UTC')"
fi

echo "==> Waiting for deployment to settle"
for _ in {1..40}; do
  status_json="$(railway deployment list \
    --project "$PROJECT_ID" \
    --environment "$ENVIRONMENT" \
    --service "$SERVICE" \
    --limit 1 \
    --json)"
  status="$(printf '%s' "$status_json" | jq -r '.[0].status')"
  deploy_id="$(printf '%s' "$status_json" | jq -r '.[0].id')"
  echo "deployment=$deploy_id status=$status"
  case "$status" in
    SUCCESS)
      echo "==> Deploy succeeded"
      exit 0
      ;;
    FAILED|CRASHED|REMOVED)
      echo "==> Deploy did not succeed; inspect Railway logs" >&2
      exit 1
      ;;
  esac
  sleep 15
done

echo "==> Timed out waiting for Railway deployment" >&2
exit 1
