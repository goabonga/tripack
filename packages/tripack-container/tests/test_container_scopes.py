# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Unit tests for :meth:`Container.scope` and :meth:`Container.ascope` (4.7)."""

from __future__ import annotations

import asyncio

import pytest

from tripack_container import Container
from tripack_contracts import Lifecycle, ScopeError


class _Cache:
    """Framework-neutral SCOPED token used across these tests."""


class _Closeable:
    """Test stand-in: records its close calls against a shared log."""

    def __init__(self, log: list[str], label: str) -> None:
        """Bind to the shared log and remember the label."""
        self._log = log
        self._label = label

    def close(self) -> None:
        """Append the label to the log on close."""
        self._log.append(self._label)


def _make_cache() -> _Cache:
    """Module-level factory for the SCOPED Cache stand-in."""
    return _Cache()


def test_scope_yields_a_scope_that_caches_a_scoped_binding() -> None:
    """SCOPED bindings share the same instance inside one container scope."""
    container = Container()
    container.bind(_Cache, _make_cache, lifecycle=Lifecycle.SCOPED)
    with container.scope():
        first = container.resolve(_Cache)
        second = container.resolve(_Cache)
    assert first is second


def test_scope_resets_active_scope_after_exit() -> None:
    """After ``with container.scope()`` exits, SCOPED resolutions fail again."""
    container = Container()
    container.bind(_Cache, _make_cache, lifecycle=Lifecycle.SCOPED)
    with container.scope():
        container.resolve(_Cache)
    with pytest.raises(ScopeError):
        container.resolve(_Cache)


def test_scope_runs_teardown_on_close_in_lifo_order() -> None:
    """SCOPED Closeable instances are torn down in reverse construction order.

    The stand-ins are inline classes that close over the shared
    log, so each token IS its own factory and the bind types
    align cleanly (no factory-returning-a-different-type
    mismatch).
    """
    log: list[str] = []

    class _First:
        """Records 'first' on close; SCOPED token registered first."""

        def close(self) -> None:
            log.append("first")

    class _Second:
        """Records 'second' on close; SCOPED token registered second."""

        def close(self) -> None:
            log.append("second")

    container = Container()
    container.bind(_First, _First, lifecycle=Lifecycle.SCOPED)
    container.bind(_Second, _Second, lifecycle=Lifecycle.SCOPED)
    with container.scope():
        container.resolve(_First)
        container.resolve(_Second)
    assert log == ["second", "first"]


def test_scope_tears_down_targets_even_when_body_raises() -> None:
    """A scope's teardown runs on the error path too."""
    log: list[str] = []

    def _make_closeable() -> _Closeable:
        return _Closeable(log, "one")

    container = Container()
    container.bind(_Closeable, _make_closeable, lifecycle=Lifecycle.SCOPED)
    with pytest.raises(RuntimeError, match="body"), container.scope():
        container.resolve(_Closeable)
        raise RuntimeError("body")
    assert log == ["one"]


def test_scope_nests_with_independent_caches() -> None:
    """An inner scope has its own cache distinct from the outer one."""
    container = Container()
    container.bind(_Cache, _make_cache, lifecycle=Lifecycle.SCOPED)
    with container.scope():
        outer = container.resolve(_Cache)
        with container.scope():
            inner = container.resolve(_Cache)
        # Outer cache is restored on inner exit.
        outer_after = container.resolve(_Cache)
    assert inner is not outer
    assert outer is outer_after


async def _ascope_caches_async_scoped() -> tuple[_Cache, _Cache]:
    """Coroutine helper for the async-scope cache test."""
    container = Container()
    container.bind(_Cache, _make_cache, lifecycle=Lifecycle.SCOPED)
    async with container.ascope():
        first = await container.aresolve(_Cache)
        second = await container.aresolve(_Cache)
    return first, second


def test_ascope_caches_scoped_bindings_across_aresolves() -> None:
    """Async scope shares SCOPED instances within one ``async with``."""
    first, second = asyncio.run(_ascope_caches_async_scoped())
    assert first is second


def test_ascope_runs_aclose_teardown_in_lifo_order() -> None:
    """``ascope`` exit awaits ``aclose`` on each registered async target.

    The async stand-ins are defined inline so each holds a
    direct closure over the shared ``log`` list, avoiding the
    factory-vs-token type mismatch a factory returning a generic
    AsyncCloseable would create.
    """
    log: list[str] = []

    class _AsyncA:
        """First async SCOPED target; records 'a' on aclose."""

        async def aclose(self) -> None:
            """Append 'a' to the shared log."""
            log.append("a")

    class _AsyncB:
        """Second async SCOPED target; records 'b' on aclose."""

        async def aclose(self) -> None:
            """Append 'b' to the shared log."""
            log.append("b")

    container = Container()
    container.bind(_AsyncA, _AsyncA, lifecycle=Lifecycle.SCOPED)
    container.bind(_AsyncB, _AsyncB, lifecycle=Lifecycle.SCOPED)

    async def _drive() -> None:
        async with container.ascope():
            container.resolve(_AsyncA)
            container.resolve(_AsyncB)

    asyncio.run(_drive())
    assert log == ["b", "a"]


async def _ascope_concurrent_isolation() -> tuple[int, int]:
    """Coroutine helper: two ``ascope`` calls under gather have distinct caches."""

    async def _worker() -> int:
        container = Container()
        container.bind(_Cache, _make_cache, lifecycle=Lifecycle.SCOPED)
        async with container.ascope():
            instance = await container.aresolve(_Cache)
            return id(instance)

    return await asyncio.gather(_worker(), _worker())


def test_ascope_concurrent_calls_have_independent_caches() -> None:
    """Two coroutines opening their own ``ascope`` see distinct SCOPED instances."""
    id_a, id_b = asyncio.run(_ascope_concurrent_isolation())
    assert id_a != id_b
