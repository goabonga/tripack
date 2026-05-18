# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Unit tests for the provider declaration helpers (4.5)."""

from __future__ import annotations

import asyncio

from tripack_container import (
    ContainerBuilder,
    async_scoped,
    async_singleton,
    async_transient,
    scoped,
    singleton,
    transient,
)
from tripack_container.providers import LIFECYCLE_ATTR
from tripack_contracts import Lifecycle


class _Clock:
    """Framework-neutral token used across these tests."""


class _Cache:
    """A second token used by the override test."""


def test_singleton_decorator_returns_the_same_function() -> None:
    """The helpers do not wrap; ``fn is decorated_fn`` holds.

    Calls ``make()`` once so its body is covered too - each test
    declares its own local ``make`` to avoid attribute collisions
    on a shared function (a previous decorator's marker would
    otherwise leak across tests).
    """

    def make() -> _Clock:
        return _Clock()

    assert isinstance(make(), _Clock)
    decorated = singleton(make)
    assert decorated is make


def test_singleton_decorator_attaches_singleton_lifecycle() -> None:
    """``@singleton`` sets ``__tripack_lifecycle__`` to SINGLETON."""

    @singleton
    def make() -> _Clock:
        return _Clock()

    assert isinstance(make(), _Clock)
    assert getattr(make, LIFECYCLE_ATTR) is Lifecycle.SINGLETON


def test_scoped_decorator_attaches_scoped_lifecycle() -> None:
    """``@scoped`` sets the marker to SCOPED."""

    @scoped
    def make() -> _Clock:
        return _Clock()

    assert isinstance(make(), _Clock)
    assert getattr(make, LIFECYCLE_ATTR) is Lifecycle.SCOPED


def test_transient_decorator_attaches_transient_lifecycle() -> None:
    """``@transient`` sets the marker to TRANSIENT (the default)."""

    @transient
    def make() -> _Clock:
        return _Clock()

    assert isinstance(make(), _Clock)
    assert getattr(make, LIFECYCLE_ATTR) is Lifecycle.TRANSIENT


def test_async_singleton_decorator_attaches_singleton_lifecycle() -> None:
    """``@async_singleton`` tags an async factory the same way."""

    @async_singleton
    async def make() -> _Clock:
        return _Clock()

    assert isinstance(asyncio.run(make()), _Clock)
    assert getattr(make, LIFECYCLE_ATTR) is Lifecycle.SINGLETON


def test_async_scoped_decorator_attaches_scoped_lifecycle() -> None:
    """``@async_scoped`` tags an async factory as SCOPED."""

    @async_scoped
    async def make() -> _Clock:
        return _Clock()

    assert isinstance(asyncio.run(make()), _Clock)
    assert getattr(make, LIFECYCLE_ATTR) is Lifecycle.SCOPED


def test_async_transient_decorator_attaches_transient_lifecycle() -> None:
    """``@async_transient`` tags an async factory as TRANSIENT."""

    @async_transient
    async def make() -> _Clock:
        return _Clock()

    assert isinstance(asyncio.run(make()), _Clock)
    assert getattr(make, LIFECYCLE_ATTR) is Lifecycle.TRANSIENT


# --- bind integration -----------------------------------------------------


def test_builder_bind_picks_up_singleton_marker_when_lifecycle_unset() -> None:
    """Without an explicit ``lifecycle=``, the marker drives the binding."""

    @singleton
    def make_clock() -> _Clock:
        return _Clock()

    container = ContainerBuilder().bind(_Clock, make_clock).build()
    first = container.resolve(_Clock)
    second = container.resolve(_Clock)
    assert first is second  # SINGLETON pick-up


def test_builder_bind_picks_up_scoped_marker_when_lifecycle_unset() -> None:
    """SCOPED marker is honored under an active lifetime scope."""
    from tripack_runtime import lifetime_scope

    @scoped
    def make_cache() -> _Cache:
        return _Cache()

    container = ContainerBuilder().bind(_Cache, make_cache).build()
    with lifetime_scope():
        first = container.resolve(_Cache)
        second = container.resolve(_Cache)
    assert first is second  # SCOPED pick-up


def test_builder_bind_explicit_lifecycle_overrides_marker() -> None:
    """Passing ``lifecycle=`` always wins over the marker on the factory."""

    @singleton
    def make_clock() -> _Clock:
        return _Clock()

    container = (
        ContainerBuilder()
        .bind(_Clock, make_clock, lifecycle=Lifecycle.TRANSIENT)
        .build()
    )
    first = container.resolve(_Clock)
    second = container.resolve(_Clock)
    assert first is not second  # explicit TRANSIENT wins over @singleton


def test_builder_bind_without_marker_defaults_to_transient() -> None:
    """An untagged factory and no ``lifecycle=`` keyword: TRANSIENT default."""

    def make_clock() -> _Clock:
        return _Clock()

    container = ContainerBuilder().bind(_Clock, make_clock).build()
    first = container.resolve(_Clock)
    second = container.resolve(_Clock)
    assert first is not second
