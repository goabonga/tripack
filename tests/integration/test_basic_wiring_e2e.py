# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""End-to-end wiring tests through the public Container API."""

from __future__ import annotations

import _fixtures as F

from tripack_container import (
    Container,
    ContainerBuilder,
)
from tripack_contracts import Lifecycle


def test_container_resolves_explicit_bindings_end_to_end() -> None:
    """A minimal container with two binds returns the right types via resolve."""
    container = Container()
    container.bind(F.Clock, F.make_clock)
    container.bind(F.Cache, F.make_cache)
    assert isinstance(container.resolve(F.Clock), F.Clock)
    assert isinstance(container.resolve(F.Cache), F.Cache)


def test_builder_produces_sealed_container_with_all_bindings() -> None:
    """``ContainerBuilder.build`` snapshots bindings into a sealed container."""
    container = (
        ContainerBuilder()
        .bind(F.Clock, F.make_clock)
        .bind(F.Cache, F.make_cache)
        .bind(F.Logger, F.make_logger, lifecycle=Lifecycle.SINGLETON)
        .build()
    )
    assert isinstance(container.resolve(F.Clock), F.Clock)
    assert isinstance(container.resolve(F.Cache), F.Cache)
    logger_a = container.resolve(F.Logger)
    logger_b = container.resolve(F.Logger)
    assert logger_a is logger_b  # SINGLETON caching across the public API


def test_module_install_composes_with_direct_bind() -> None:
    """A :class:`Module` runs its register() and coexists with later direct binds."""
    container = (
        ContainerBuilder().install(F.AppModule()).bind(F.Logger, F.make_logger).build()
    )
    assert isinstance(container.resolve(F.Clock), F.Clock)
    assert isinstance(container.resolve(F.Cache), F.Cache)
    assert isinstance(container.resolve(F.Logger), F.Logger)


def test_auto_injection_resolves_constructor_params_through_container() -> None:
    """``bind_class`` walks the constructor and pulls each dep from the container."""
    container = (
        ContainerBuilder()
        .bind(F.Clock, F.make_clock)
        .bind(F.Cache, F.make_cache)
        .bind_class(F.App)
        .build()
    )
    app = container.resolve(F.App)
    assert isinstance(app.clock, F.Clock)
    assert isinstance(app.cache, F.Cache)
