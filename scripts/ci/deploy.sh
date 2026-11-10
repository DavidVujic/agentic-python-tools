#!/usr/bin/env bash

# Install built artifacts (wheel with --no-deps, then requirements.txt) into a throwaway
# venv and smoke-test them (version match, top-level import, pip check; entry points printed).

# CI: the `deploy` job attaches the workspace first, then runs this.
# Locally: bash scripts/ci/build.sh first, then bash scripts/ci/deploy.sh

set -euo pipefail

ARTIFACTS_DIR="${ARTIFACTS_DIR:-artifacts}"
VENV_DIR="${VENV_DIR:-.venv-deploy}"

if [[ ! -d "$ARTIFACTS_DIR" ]]; then
  echo "No $ARTIFACTS_DIR directory; run scripts/ci/build.sh first" >&2
  exit 1
fi

shopt -s nullglob
found=0
for d in "$ARTIFACTS_DIR"/*/; do found=1; break; done
if [[ "$found" -eq 0 ]]; then
  echo "No built projects in $ARTIFACTS_DIR; nothing to deploy"
  exit 0
fi

uv venv "$VENV_DIR" -q
PY="$VENV_DIR/bin/python"

for d in "$ARTIFACTS_DIR"/*/; do
  p="$(basename "$d")"
  whl="$(ls "$d"/*.whl)"
  echo "Installing $p from $whl"
  uv pip install --python "$PY" --no-deps "$whl"
  uv pip install --python "$PY" -r "$d/requirements.txt"
  uv pip check --python "$PY"
  dist="$(basename "$whl" | cut -d- -f1 | tr '_' '-')"
  ver="$(basename "$whl" | cut -d- -f2)"
  DIST="$dist" VER="$ver" "$PY" - <<'PY'
import importlib, importlib.metadata as m, os


dist, ver = os.environ["DIST"], os.environ["VER"]
d = m.distribution(dist)

assert d.version == ver, (dist, d.version, ver)

top = ((d.read_text("top_level.txt") or "").split() or [dist.replace("-", "_")])[0]

importlib.import_module(top)

eps = [e.name for e in d.entry_points]
print(f"{dist} {d.version}: import {top} ok; entry points: {eps or 'none'}")
PY

done
