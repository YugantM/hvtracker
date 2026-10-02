#!/bin/bash
set -euo pipefail

# The PR gates, in one command. The same checks CI runs (.github/workflows/ci.yml),
# cheapest first, so a green run here means a green PR.
#
# Typing the raw commands by hand is unreliable:
#   * bare `python` is not on PATH, and the system python3 has none of the
#     project's dependencies. The toolchain lives in .venv.
#   * `--render-only` rewrites tracked generated artifacts. Left dirty they get
#     committed by accident, but blindly restoring them would clobber real
#     edits, so this restores only the paths the run itself dirtied.

cd "$(dirname "$0")/.."

if [ -n "${VIRTUAL_ENV:-}" ] && [ -x "$VIRTUAL_ENV/bin/python" ]; then
  PY="$VIRTUAL_ENV/bin/python"
elif [ -x .venv/bin/python ]; then
  PY=.venv/bin/python
else
  PY=python3
fi

# Rewritten by --render-only, tracked in git, and never a deliberate edit
# during a gate run.
CHURN_PATHS=(data/render_state.json og-v2.png scorecard-cache.json)

# Anything already dirty is the caller's work. The render rewrites these files
# regardless, so back them up now and put them back afterwards, exactly as found.
preexisting_dirty=()
backup_dir="$(mktemp -d)"
for path in "${CHURN_PATHS[@]}"; do
  if ! git diff --quiet -- "$path"; then
    preexisting_dirty+=("$path")
    mkdir -p "$backup_dir/$(dirname "$path")"
    cp -p "$path" "$backup_dir/$path"
  fi
done

restore_churn() {
  local path
  for path in "${CHURN_PATHS[@]}"; do
    if [ -f "$backup_dir/$path" ]; then
      cp -p "$backup_dir/$path" "$path"
    else
      git checkout -- "$path" 2>/dev/null || true
    fi
  done
  rm -rf "$backup_dir"
}
trap restore_churn EXIT

echo "=== 1/4 ruff ==="
"$PY" -m ruff check .

echo "=== 2/4 pytest ==="
"$PY" -m pytest -q

echo "=== 3/4 render-only build ==="
"$PY" fetch_and_build.py --render-only

echo "=== 4/4 validate rendered HTML ==="
"$PY" tests/validate_html.py

restore_churn
trap - EXIT

echo
echo "=== All gates passed ==="
if [ "${#preexisting_dirty[@]}" -gt 0 ]; then
  echo "Kept your edits (dirty before this run): ${preexisting_dirty[*]}"
fi
# A local render reports a board-invariant "mass churn" violation because the
# local board isn't production's; check production's /data/build_report.json.
remaining="$(git status --porcelain)"
if [ -n "$remaining" ]; then
  echo
  echo "Working tree still has changes (review before committing):"
  echo "$remaining"
fi
