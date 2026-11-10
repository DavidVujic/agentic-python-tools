#!/usr/bin/env bash

# Run pytest only for bricks changed since the latest stable-* tag.

# CI: used by the `test-changed` job.
# Optional - Locally: POLY_SINCE=v0.0.6 bash scripts/ci/test-changed.sh

set -euo pipefail

since_args=()
if [[ -n "${POLY_SINCE:-}" ]]; then
  since_args=(--since "$POLY_SINCE")
fi

changes="$(uv run poly diff --bricks --short ${since_args[@]+"${since_args[@]}"})"
if [[ -z "$changes" ]] || [[ "$changes" = "No matching tags or commits found in repository." ]]; then
  echo "No changed bricks since the latest tag; nothing to run"
  exit 0
fi

query="${changes//,/ or }"
echo "Changed bricks: $changes -> pytest -m \"$query\""
uv run pytest -m "$query" -q || [[ $? -eq 5 ]]
