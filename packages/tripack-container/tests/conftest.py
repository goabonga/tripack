# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Per-package test fixtures and ``sys.path`` setup.

The TOML / JSON / YAML configuration loaders resolve dotted
Python names via :func:`importlib.import_module`, and the tests
that exercise them keep their importable test fixtures in a
sibling module (``_config_fixtures.py``). Without an
``__init__.py`` in this directory (pytest is run in
``importlib`` import mode), the directory is not on
``sys.path`` automatically, so the loader cannot find the
fixtures. Inserting the tests directory at conftest-collection
time fixes that without polluting the production package.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
