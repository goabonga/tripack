# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Public API of the Tripack dependency-injection runtime.

This module re-exports the stable surface of ``tripack_runtime``.
Symbols not listed in :data:`__all__` are internal and may change at
any time without prior notice.
"""

from tripack_runtime.__version__ import __version__
from tripack_runtime.binding import Binding
from tripack_runtime.context import (
    ResolutionContext,
    aresolution_scope,
    current_context,
    resolution_scope,
)
from tripack_runtime.graph import DependencyGraph

__all__ = [
    "Binding",
    "DependencyGraph",
    "ResolutionContext",
    "__version__",
    "aresolution_scope",
    "current_context",
    "resolution_scope",
]
