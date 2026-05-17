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
from tripack_runtime.cycles import (
    aguarded_resolving,
    check_for_cycle,
    guarded_resolving,
)
from tripack_runtime.graph import DependencyGraph
from tripack_runtime.resolver import Resolver
from tripack_runtime.scope import (
    Scope,
    alifetime_scope,
    current_scope,
    lifetime_scope,
)

__all__ = [
    "Binding",
    "DependencyGraph",
    "ResolutionContext",
    "Resolver",
    "Scope",
    "__version__",
    "aguarded_resolving",
    "alifetime_scope",
    "aresolution_scope",
    "check_for_cycle",
    "current_context",
    "current_scope",
    "guarded_resolving",
    "lifetime_scope",
    "resolution_scope",
]
