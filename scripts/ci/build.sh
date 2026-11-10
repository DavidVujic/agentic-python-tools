#!/usr/bin/env bash

# Build a wheel + requirements.txt per project changed since the latest tag.
# Artifacts land in $ARTIFACTS_DIR (default: artifacts), plus manifest.txt listing them.

# CI: used by the `build` job (manifest guarantees persist_to_workspace always has a root).
# Optional - Locally: POLY_SINCE=v0.0.6 bash scripts/ci/build.sh

set -euo pipefail

ARTIFACTS_DIR="${ARTIFACTS_DIR:-artifacts}"
mkdir -p "$ARTIFACTS_DIR"
manifest="$ARTIFACTS_DIR/manifest.txt"
: > "$manifest"

since_args=()
if [[ -n "${POLY_SINCE:-}" ]]; then
  since_args=(--since "$POLY_SINCE")
fi

projects="$(uv run poly diff --short ${since_args[@]+"${since_args[@]}"})"
if [[ -z "$projects" ]] || [[ "$projects" = "No matching tags or commits found in repository." ]]; then
  echo "No changed projects since the latest tag; nothing to build"
  exit 0
fi

for p in ${projects//,/ }; do
  echo "Building $p"
  echo "$p" >> "$manifest"
  uv build --package "$p" --out-dir "$ARTIFACTS_DIR/$p"
  uv export --package "$p" --no-dev --no-emit-project --format requirements.txt -o "$ARTIFACTS_DIR/$p/requirements.txt"
  rm -f "$ARTIFACTS_DIR/$p/.gitignore"
done

ls -R "$ARTIFACTS_DIR"
