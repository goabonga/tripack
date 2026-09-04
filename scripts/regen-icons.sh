#!/usr/bin/env bash

# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

# Regenerate every derived branding asset from the canonical SVG at
# `assets/tripack.svg`. Re-run after editing the master SVG and commit
# the outputs - the docs job builds the site from the checked-in files
# and never runs this script.
#
# Outputs:
#   docs/tripack.svg   site logo   (zensical `[project.theme].logo`)
#   docs/favicon.ico   site icon   (zensical `[project.theme].favicon`)
#
# Favicon conversion delegates to `scripts/generate_favicon.py`
# (cairosvg + Pillow), pinned in the workspace's `favicon` dep group.

set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
SRC="$ROOT/assets/tripack.svg"

if [[ ! -f "$SRC" ]]; then
  echo "regen-icons: missing $SRC" >&2
  exit 1
fi

# Zensical resolves theme assets relative to the docs dir, so the master
# SVG is copied rather than referenced across directories.
cp "$SRC" "$ROOT/docs/tripack.svg"

# `--only-group favicon` keeps the native cairo stack out of the default
# dev environment; the group exists solely for this call.
uv run --only-group favicon python "$ROOT/scripts/generate_favicon.py" \
  -i "$ROOT/docs/tripack.svg" \
  -o "$ROOT/docs/favicon.ico"

echo "regen-icons: docs/tripack.svg + docs/favicon.ico from $SRC"
