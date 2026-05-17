# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Unit tests for teardown propagation across Scope and Resolver."""

from __future__ import annotations

import asyncio

import pytest

from tripack_contracts import Lifecycle
from tripack_runtime import (
    Binding,
    DependencyGraph,
    Resolver,
    Scope,
    alifetime_scope,
    lifetime_scope,
)


class _SyncCloseTracker:
    """Test stand-in: records each ``close`` call against a shared log."""

    def __init__(self, log: list[str], label: str) -> None:
        """Bind to the shared log and remember the label to record."""
        self._log = log
        self._label = label

    def close(self) -> None:
        """Append the bound label to the log."""
        self._log.append(self._label)


class _AsyncCloseTracker:
    """Test stand-in: records each ``aclose`` call against a shared log."""

    def __init__(self, log: list[str], label: str) -> None:
        """Bind to the shared log and remember the label to record."""
        self._log = log
        self._label = label

    async def aclose(self) -> None:
        """Append the bound label to the log."""
        self._log.append(self._label)


class _DualCloseTracker:
    """Test stand-in with both ``close`` and ``aclose``.

    Used to verify the async-path preference (``aclose`` wins
    when both are present) and to exercise the dual code path
    on the sync side as well.
    """

    def __init__(self, log: list[str], label: str) -> None:
        """Bind to the shared log and remember the label to record."""
        self._log = log
        self._label = label

    def close(self) -> None:
        """Record a sync-path teardown."""
        self._log.append(f"sync:{self._label}")

    async def aclose(self) -> None:
        """Record an async-path teardown (preferred when both exist)."""
        self._log.append(f"async:{self._label}")


class _RaisingCloseable:
    """Test stand-in whose ``close`` always raises."""

    def __init__(self, message: str) -> None:
        """Bind the exception message ``close`` will raise."""
        self._message = message

    def close(self) -> None:
        """Always raise the bound message wrapped as :class:`RuntimeError`."""
        raise RuntimeError(self._message)


class _RaisingAsyncCloseable:
    """Test stand-in whose ``aclose`` always raises."""

    def __init__(self, message: str) -> None:
        """Bind the exception message ``aclose`` will raise."""
        self._message = message

    async def aclose(self) -> None:
        """Always raise the bound message wrapped as :class:`RuntimeError`."""
        raise RuntimeError(self._message)


# --- Scope.close ----------------------------------------------------------


def test_scope_close_invokes_targets_in_lifo_order() -> None:
    """Teardown runs in reverse of registration order."""
    log: list[str] = []
    scope = Scope()
    scope.remember("first", _SyncCloseTracker(log, "first"))
    scope.remember("second", _SyncCloseTracker(log, "second"))
    scope.remember("third", _SyncCloseTracker(log, "third"))
    scope.close()
    assert log == ["third", "second", "first"]


def test_scope_close_is_a_noop_on_empty_scope() -> None:
    """A scope without teardowns closes silently."""
    scope = Scope()
    scope.close()
    scope.close()  # second call also silent


def test_scope_close_is_idempotent_on_second_call() -> None:
    """A second ``close`` after the first does nothing."""
    log: list[str] = []
    scope = Scope()
    scope.remember("only", _SyncCloseTracker(log, "only"))
    scope.close()
    scope.close()
    assert log == ["only"]  # not ["only", "only"]


def test_scope_close_skips_async_only_targets_silently() -> None:
    """A target exposing only ``aclose`` is skipped by sync ``close``."""
    log: list[str] = []
    scope = Scope()
    scope.remember("async-only", _AsyncCloseTracker(log, "async-only"))
    scope.remember("sync", _SyncCloseTracker(log, "sync"))
    scope.close()
    assert log == ["sync"]


def test_scope_close_uses_sync_method_on_dual_targets() -> None:
    """Sync ``close`` picks ``close`` even when ``aclose`` also exists."""
    log: list[str] = []
    scope = Scope()
    scope.remember("dual", _DualCloseTracker(log, "dual"))
    scope.close()
    assert log == ["sync:dual"]


def test_scope_close_collects_errors_into_exception_group() -> None:
    """A failing ``close`` does not prevent siblings from running."""
    log: list[str] = []
    scope = Scope()
    scope.remember("before", _SyncCloseTracker(log, "before"))
    scope.remember("bad", _RaisingCloseable("kaboom"))
    scope.remember("after", _SyncCloseTracker(log, "after"))
    with pytest.raises(ExceptionGroup) as exc_info:
        scope.close()
    assert any(
        isinstance(e, RuntimeError) and str(e) == "kaboom"
        for e in exc_info.value.exceptions
    )
    assert log == ["after", "before"]


# --- Scope.aclose ---------------------------------------------------------


async def _aclose_runs_lifo() -> list[str]:
    """Coroutine helper for the LIFO aclose test."""
    log: list[str] = []
    scope = Scope()
    scope.remember("first", _AsyncCloseTracker(log, "first"))
    scope.remember("second", _AsyncCloseTracker(log, "second"))
    scope.remember("third", _SyncCloseTracker(log, "third"))
    await scope.aclose()
    return log


def test_scope_aclose_invokes_lifo() -> None:
    """``aclose`` walks LIFO and handles both sync and async targets."""
    log = asyncio.run(_aclose_runs_lifo())
    assert log == ["third", "second", "first"]


async def _aclose_prefers_aclose_over_close() -> list[str]:
    """Coroutine helper for the dual-target preference test."""
    log: list[str] = []
    scope = Scope()
    scope.remember("dual", _DualCloseTracker(log, "dual"))
    await scope.aclose()
    return log


def test_scope_aclose_prefers_aclose_when_both_methods_exist() -> None:
    """A target with both ``close`` and ``aclose`` is awaited, not called."""
    log = asyncio.run(_aclose_prefers_aclose_over_close())
    assert log == ["async:dual"]


async def _aclose_idempotent() -> list[str]:
    """Coroutine helper for the async idempotence test."""
    log: list[str] = []
    scope = Scope()
    scope.remember("only", _AsyncCloseTracker(log, "only"))
    await scope.aclose()
    await scope.aclose()
    return log


def test_scope_aclose_is_idempotent_on_second_call() -> None:
    """A second ``aclose`` after the first is a no-op."""
    log = asyncio.run(_aclose_idempotent())
    assert log == ["only"]


def test_scope_aclose_collects_async_errors_into_exception_group() -> None:
    """A failing ``aclose`` does not prevent siblings from running."""
    log: list[str] = []

    async def _go() -> None:
        scope = Scope()
        scope.remember("before", _AsyncCloseTracker(log, "before"))
        scope.remember("bad", _RaisingAsyncCloseable("async-kaboom"))
        scope.remember("after", _AsyncCloseTracker(log, "after"))
        await scope.aclose()

    with pytest.raises(ExceptionGroup) as exc_info:
        asyncio.run(_go())
    assert any(
        isinstance(e, RuntimeError) and str(e) == "async-kaboom"
        for e in exc_info.value.exceptions
    )
    assert log == ["after", "before"]


def test_scope_aclose_collects_sync_close_errors_during_async_teardown() -> None:
    """A sync-only target whose ``close`` raises is captured by ``aclose`` too."""
    log: list[str] = []

    async def _go() -> None:
        scope = Scope()
        scope.remember("ok", _AsyncCloseTracker(log, "ok"))
        scope.remember("bad", _RaisingCloseable("sync-fail-in-async"))
        await scope.aclose()

    with pytest.raises(ExceptionGroup) as exc_info:
        asyncio.run(_go())
    assert any(
        isinstance(e, RuntimeError) and str(e) == "sync-fail-in-async"
        for e in exc_info.value.exceptions
    )
    assert log == ["ok"]


# --- lifetime_scope / alifetime_scope auto-close --------------------------


def test_lifetime_scope_auto_closes_targets_on_normal_exit() -> None:
    """The sync context manager calls ``close`` for each registered target."""
    log: list[str] = []
    with lifetime_scope() as scope:
        scope.remember("first", _SyncCloseTracker(log, "first"))
        scope.remember("second", _SyncCloseTracker(log, "second"))
    assert log == ["second", "first"]


def test_lifetime_scope_auto_closes_targets_even_when_body_raises() -> None:
    """Teardown happens on the error path too, so resources do not leak."""
    log: list[str] = []
    with (
        pytest.raises(RuntimeError, match="body"),
        lifetime_scope() as scope,
    ):
        scope.remember("only", _SyncCloseTracker(log, "only"))
        raise RuntimeError("body")
    assert log == ["only"]


async def _alifetime_scope_auto_acloses() -> list[str]:
    """Coroutine helper for the async auto-aclose test."""
    log: list[str] = []
    async with alifetime_scope() as scope:
        scope.remember("first", _AsyncCloseTracker(log, "first"))
        scope.remember("second", _SyncCloseTracker(log, "second"))
    return log


def test_alifetime_scope_auto_acloses_targets_on_normal_exit() -> None:
    """The async context manager awaits ``aclose`` for each registered target."""
    log = asyncio.run(_alifetime_scope_auto_acloses())
    assert log == ["second", "first"]


def test_alifetime_scope_acloses_even_when_body_raises() -> None:
    """Async teardown happens on the error path too."""
    log: list[str] = []

    async def _go() -> None:
        async with alifetime_scope() as scope:
            scope.remember("only", _AsyncCloseTracker(log, "only"))
            raise RuntimeError("body")

    with pytest.raises(RuntimeError, match="body"):
        asyncio.run(_go())
    assert log == ["only"]


# --- Resolver.close / aclose ---------------------------------------------


def test_resolver_close_invokes_singleton_teardowns_in_lifo_order() -> None:
    """The resolver tears down its SINGLETON targets in reverse insertion order."""
    log: list[str] = []

    class _First:
        """Token for the first SINGLETON."""

    class _Second:
        """Token for the second SINGLETON."""

    def _factory_first() -> _SyncCloseTracker:
        return _SyncCloseTracker(log, "first")

    def _factory_second() -> _SyncCloseTracker:
        return _SyncCloseTracker(log, "second")

    graph = DependencyGraph()
    graph.register(
        Binding(token=_First, factory=_factory_first, lifecycle=Lifecycle.SINGLETON)
    )
    graph.register(
        Binding(token=_Second, factory=_factory_second, lifecycle=Lifecycle.SINGLETON)
    )
    resolver = Resolver(graph)
    resolver.resolve(_First)
    resolver.resolve(_Second)
    resolver.close()
    assert log == ["second", "first"]


def test_resolver_close_is_idempotent_on_second_call() -> None:
    """A second ``close`` after the first is a no-op."""
    log: list[str] = []

    class _Token:
        """Token for the only SINGLETON in this test."""

    def _factory() -> _SyncCloseTracker:
        return _SyncCloseTracker(log, "only")

    graph = DependencyGraph()
    graph.register(
        Binding(token=_Token, factory=_factory, lifecycle=Lifecycle.SINGLETON)
    )
    resolver = Resolver(graph)
    resolver.resolve(_Token)
    resolver.close()
    resolver.close()
    assert log == ["only"]


def test_resolver_close_skips_async_only_singleton_targets_silently() -> None:
    """``close`` on the resolver also skips async-only singleton instances."""
    log: list[str] = []

    class _Token:
        """Token for the async-only SINGLETON."""

    def _factory() -> _AsyncCloseTracker:
        return _AsyncCloseTracker(log, "async-only")

    graph = DependencyGraph()
    graph.register(
        Binding(token=_Token, factory=_factory, lifecycle=Lifecycle.SINGLETON)
    )
    resolver = Resolver(graph)
    resolver.resolve(_Token)
    resolver.close()
    assert log == []  # the async-only target was skipped


async def _aresolve_close_async_singleton() -> list[str]:
    """Coroutine helper for the async resolver teardown test."""
    log: list[str] = []

    class _Token:
        """Token for the async SINGLETON."""

    async def _factory() -> _AsyncCloseTracker:
        return _AsyncCloseTracker(log, "async-only")

    graph = DependencyGraph()
    graph.register(
        Binding(
            token=_Token,
            async_factory=_factory,
            lifecycle=Lifecycle.SINGLETON,
        )
    )
    resolver = Resolver(graph)
    await resolver.aresolve(_Token)
    await resolver.aclose()
    return log


def test_resolver_aclose_awaits_async_singleton_teardown() -> None:
    """``aclose`` on the resolver handles async-only singleton targets."""
    log = asyncio.run(_aresolve_close_async_singleton())
    assert log == ["async-only"]


async def _aclose_idempotent_on_resolver() -> list[str]:
    """Coroutine helper for the async resolver idempotence test."""
    log: list[str] = []

    class _Token:
        """Token for the async SINGLETON."""

    async def _factory() -> _AsyncCloseTracker:
        return _AsyncCloseTracker(log, "only")

    graph = DependencyGraph()
    graph.register(
        Binding(
            token=_Token,
            async_factory=_factory,
            lifecycle=Lifecycle.SINGLETON,
        )
    )
    resolver = Resolver(graph)
    await resolver.aresolve(_Token)
    await resolver.aclose()
    await resolver.aclose()
    return log


def test_resolver_aclose_is_idempotent_on_second_call() -> None:
    """A second ``aclose`` after the first is a no-op."""
    log = asyncio.run(_aclose_idempotent_on_resolver())
    assert log == ["only"]


# --- Cross-instance teardown isolation ------------------------------------


def test_lifetime_scope_does_not_close_singleton_targets() -> None:
    """A SINGLETON cached on the resolver is not touched by scope exit.

    The scope's teardown list only contains SCOPED instances;
    SINGLETON teardowns live on the resolver and survive the
    scope's lifetime.
    """
    log: list[str] = []

    class _Scoped:
        """SCOPED token."""

    class _Singleton:
        """SINGLETON token."""

    def _scoped_factory() -> _SyncCloseTracker:
        return _SyncCloseTracker(log, "scoped")

    def _singleton_factory() -> _SyncCloseTracker:
        return _SyncCloseTracker(log, "singleton")

    graph = DependencyGraph()
    graph.register(
        Binding(token=_Scoped, factory=_scoped_factory, lifecycle=Lifecycle.SCOPED)
    )
    graph.register(
        Binding(
            token=_Singleton,
            factory=_singleton_factory,
            lifecycle=Lifecycle.SINGLETON,
        )
    )
    resolver = Resolver(graph)
    with lifetime_scope():
        resolver.resolve(_Scoped)
        resolver.resolve(_Singleton)
    # Scope exit closed only the SCOPED instance.
    assert log == ["scoped"]
    # The SINGLETON survives; the resolver still owns its teardown.
    resolver.close()
    assert log == ["scoped", "singleton"]


def test_scope_close_does_not_clear_the_cache() -> None:
    """``close`` runs teardowns but leaves cached values readable.

    Useful for post-mortem inspection of what was built.
    """
    log: list[str] = []
    scope = Scope()
    tracker = _SyncCloseTracker(log, "only")
    scope.remember("only", tracker)
    scope.close()
    assert scope.lookup("only") is tracker
