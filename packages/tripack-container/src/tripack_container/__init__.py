# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Public API of the Tripack IoC container.

This module re-exports the stable surface of
``tripack_container``. Symbols not listed in :data:`__all__`
are internal and may change at any time without prior notice.
"""

from tripack_container.__version__ import __version__
from tripack_container.builder import ContainerBuilder
from tripack_container.container import Container
from tripack_container.module import Module
from tripack_container.providers import (
    async_scoped,
    async_singleton,
    async_transient,
    inject,
    scoped,
    singleton,
    transient,
)

__all__ = [
    "Container",
    "ContainerBuilder",
    "Module",
    "__version__",
    "async_scoped",
    "async_singleton",
    "async_transient",
    "inject",
    "scoped",
    "singleton",
    "transient",
]
