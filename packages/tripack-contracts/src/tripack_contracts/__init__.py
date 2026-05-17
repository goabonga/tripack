# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Public API of the Tripack dependency-injection contracts package.

This module re-exports the stable surface of ``tripack_contracts``.
Symbols not listed in :data:`__all__` are internal and may change at
any time without prior notice.
"""

from tripack_contracts.__version__ import __version__
from tripack_contracts.closeable import AsyncCloseable, Closeable
from tripack_contracts.config import BindingSpec, ContainerConfig
from tripack_contracts.errors import (
    BindingError,
    CircularDependencyError,
    ConfigurationError,
    ResolutionError,
    ScopeError,
    TripackError,
)
from tripack_contracts.lifecycle import Lifecycle
from tripack_contracts.provider import AsyncProvider, Provider
from tripack_contracts.resolver import AsyncResolver, Resolver
from tripack_contracts.types import DependencyToken

__all__ = [
    "AsyncCloseable",
    "AsyncProvider",
    "AsyncResolver",
    "BindingError",
    "BindingSpec",
    "CircularDependencyError",
    "Closeable",
    "ConfigurationError",
    "ContainerConfig",
    "DependencyToken",
    "Lifecycle",
    "Provider",
    "ResolutionError",
    "Resolver",
    "ScopeError",
    "TripackError",
    "__version__",
]
