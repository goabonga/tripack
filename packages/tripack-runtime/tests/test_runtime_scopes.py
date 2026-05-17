# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Unit tests for the lifetime scope and the SCOPED lifecycle dispatch."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from tripack_contracts import (
    CircularDependencyError,
    Lifecycle,
    ScopeError,
)
from tripack_runtime import (
    Binding,
    DependencyGraph,
    Resolver,
    Scope,
    alifetime_scope,
    current_scope,
    lifetime_scope,
)


class _Clock:
    """Framework-neutral token used across these tests."""


class _Closeable:
    """Test stand-in: structurally satisfies the sync close contract."""

    def __init__(self) -> None:
        """Track invocations so the smoke-test can observe them."""
        self.close_calls = 0

    def close(self) -> None:
        """Idempotent bump of the call counter."""
        self.close_calls += 1


class _AsyncCloseable:
    """Test stand-in: structurally satisfies the async aclose contract."""

    def __init__(self) -> None:
        """Track invocations so the smoke-test can observe them."""
        self.aclose_calls = 0

    async def aclose(self) -> None:
        """Idempotent bump of the call counter."""
        self.aclose_calls += 1


class _PlainService:
    """Test stand-in without close/aclose: nothing to register."""


async def _async_clock_factory() -> _Clock:
    """Module-level async factory reused across the async SCOPED tests."""
    return _Clock()


# --- Scope object ---------------------------------------------------------


def test_new_scope_starts_empty() -> None:
    """A fresh :class:`Scope` reports no teardowns."""
    scope = Scope()
    assert scope.teardowns() == ()


def test_scope_uses_slots_not_dict() -> None:
    """``__slots__`` keeps the scope free of per-instance dict."""
    scope = Scope()
    assert not hasattr(scope, "__dict__")


def test_scope_remember_caches_for_subsequent_lookup() -> None:
    """An instance handed to ``remember`` becomes the next ``lookup`` result."""
    scope = Scope()
    instance = _Clock()
    scope.remember(_Clock, instance)
    assert scope.lookup(_Clock) is instance


def test_scope_remember_registers_closeable_for_teardown() -> None:
    """A cached Closeable lands in the teardown list."""
    scope = Scope()
    instance = _Closeable()
    scope.remember(_Closeable, instance)
    assert scope.teardowns() == (instance,)


def test_scope_remember_does_not_register_plain_services() -> None:
    """An instance without close/aclose is cached but not registered."""
    scope = Scope()
    scope.remember(_PlainService, _PlainService())
    assert scope.teardowns() == ()


def test_scope_remember_preserves_insertion_order() -> None:
    """Multiple registrations appear in the order they were added."""
    scope = Scope()
    a = _Closeable()
    b = _AsyncCloseable()
    scope.remember(_Closeable, a)
    scope.remember(_AsyncCloseable, b)
    assert scope.teardowns() == (a, b)


# --- ContextVar wiring ----------------------------------------------------


def test_current_scope_is_none_outside_any_lifetime_scope() -> None:
    """Without an open scope, ``current_scope`` is ``None``."""
    assert current_scope() is None


def test_lifetime_scope_binds_current_scope_for_block_duration() -> None:
    """Inside the block, ``current_scope`` returns the active one."""
    with lifetime_scope() as scope:
        assert current_scope() is scope
    assert current_scope() is None


def test_lifetime_scope_nests_correctly() -> None:
    """Inner scope shadows outer; outer is restored on exit."""
    with lifetime_scope() as outer:
        with lifetime_scope() as inner:
            assert current_scope() is inner
            assert inner is not outer
        assert current_scope() is outer
    assert current_scope() is None


async def _alifetime_scope_binds_current_scope() -> bool:
    """Coroutine helper covered by :func:`test_alifetime_scope_binds_current_scope`."""
    async with alifetime_scope() as scope:
        return current_scope() is scope


def test_alifetime_scope_binds_current_scope() -> None:
    """The async scope manager binds the ContextVar the same way."""
    assert asyncio.run(_alifetime_scope_binds_current_scope())


async def _concurrent_scopes(label: str) -> tuple[int, str]:
    """Coroutine helper for :func:`test_concurrent_async_scopes_are_independent`.

    Yields once mid-scope so the scheduler can run the sibling
    in between; the returned scope id proves the two coroutines
    never shared a :class:`Scope`.
    """
    async with alifetime_scope() as scope:
        scope.remember(label, object())
        await asyncio.sleep(0)
        return id(scope), label


async def _run_two_concurrent_scopes() -> tuple[tuple[int, str], tuple[int, str]]:
    """Run two scope-opening coroutines under :func:`asyncio.gather`."""
    return await asyncio.gather(_concurrent_scopes("A"), _concurrent_scopes("B"))


def test_concurrent_async_scopes_are_independent() -> None:
    """Two coroutines under ``gather`` each observe their own scope."""
    (id_a, label_a), (id_b, label_b) = asyncio.run(_run_two_concurrent_scopes())
    assert id_a != id_b
    assert label_a == "A"
    assert label_b == "B"


# --- Resolver SCOPED dispatch (sync) --------------------------------------


def test_scoped_resolve_without_active_scope_raises_scope_error() -> None:
    """Resolving a SCOPED token outside any scope is a configuration error."""
    graph = DependencyGraph()
    graph.register(Binding(token=_Clock, factory=_Clock, lifecycle=Lifecycle.SCOPED))
    resolver = Resolver(graph)
    with pytest.raises(ScopeError, match="SCOPED lifecycle but no scope"):
        resolver.resolve(_Clock)


def test_scoped_resolve_returns_same_instance_within_the_same_scope() -> None:
    """Two SCOPED resolves inside one scope share the instance."""
    graph = DependencyGraph()
    graph.register(Binding(token=_Clock, factory=_Clock, lifecycle=Lifecycle.SCOPED))
    resolver = Resolver(graph)
    with lifetime_scope():
        first = resolver.resolve(_Clock)
        second = resolver.resolve(_Clock)
    assert first is second


def test_scoped_resolve_returns_distinct_instances_across_scopes() -> None:
    """Each scope has its own cache; different scopes produce different instances."""
    graph = DependencyGraph()
    graph.register(Binding(token=_Clock, factory=_Clock, lifecycle=Lifecycle.SCOPED))
    resolver = Resolver(graph)
    with lifetime_scope():
        first = resolver.resolve(_Clock)
    with lifetime_scope():
        second = resolver.resolve(_Clock)
    assert first is not second


def test_scoped_resolve_caches_on_the_active_scope() -> None:
    """The instance is placed on the scope returned by ``current_scope``."""
    graph = DependencyGraph()
    graph.register(
        Binding(token=_Closeable, factory=_Closeable, lifecycle=Lifecycle.SCOPED)
    )
    resolver = Resolver(graph)
    with lifetime_scope() as scope:
        instance = resolver.resolve(_Closeable)
        assert scope.lookup(_Closeable) is instance


def test_scoped_resolve_registers_closeable_on_the_scope_not_the_resolver() -> None:
    """SCOPED teardown targets live on the scope, not the resolver-level list.

    Also smoke-tests the stand-in by calling ``close`` on the
    registered target, matching the pattern from the singleton
    suite.
    """
    graph = DependencyGraph()
    graph.register(
        Binding(token=_Closeable, factory=_Closeable, lifecycle=Lifecycle.SCOPED)
    )
    resolver = Resolver(graph)
    with lifetime_scope() as scope:
        instance = resolver.resolve(_Closeable)
        assert scope.teardowns() == (instance,)
        instance.close()
        assert instance.close_calls == 1
    # Resolver-level teardowns are still empty: SCOPED never feeds them.
    assert resolver.teardowns() == ()


def test_scoped_self_referential_factory_raises_cycle_error() -> None:
    """A SCOPED factory that recursively resolves itself trips the guard.

    The cycle prevents construction entirely, so the scope's
    teardown list stays empty and a retry within the same scope
    re-invokes the factory.
    """
    graph = DependencyGraph()
    resolver: Resolver

    def _factory() -> Any:
        resolver.resolve(_Clock)

    graph.register(Binding(token=_Clock, factory=_factory, lifecycle=Lifecycle.SCOPED))
    resolver = Resolver(graph)
    with lifetime_scope() as scope:
        with pytest.raises(CircularDependencyError) as exc_info:
            resolver.resolve(_Clock)
        assert scope.teardowns() == ()
    assert exc_info.value.cycle == (_Clock, _Clock)


def test_scoped_factory_error_leaves_the_scope_cache_empty() -> None:
    """A factory that raises does not poison the SCOPED cache."""
    attempt = {"count": 0}

    def _factory() -> _Clock:
        attempt["count"] += 1
        if attempt["count"] == 1:
            raise RuntimeError("first call fails")
        return _Clock()

    graph = DependencyGraph()
    graph.register(Binding(token=_Clock, factory=_factory, lifecycle=Lifecycle.SCOPED))
    resolver = Resolver(graph)
    with lifetime_scope() as scope:
        with pytest.raises(RuntimeError, match="first call fails"):
            resolver.resolve(_Clock)
        assert scope.teardowns() == ()
        # Second call succeeds and is cached for the rest of the scope.
        instance = resolver.resolve(_Clock)
        assert resolver.resolve(_Clock) is instance


# --- Resolver SCOPED dispatch (async) -------------------------------------


async def _aresolve_scoped_twice() -> tuple[_Clock, _Clock]:
    """Helper for the async SCOPED-cache test."""
    graph = DependencyGraph()
    graph.register(
        Binding(
            token=_Clock,
            async_factory=_async_clock_factory,
            lifecycle=Lifecycle.SCOPED,
        )
    )
    resolver = Resolver(graph)
    async with alifetime_scope():
        first = await resolver.aresolve(_Clock)
        second = await resolver.aresolve(_Clock)
    return first, second


def test_aresolve_scoped_returns_same_instance_within_one_scope() -> None:
    """SCOPED via async factory shares the instance within one async scope."""
    first, second = asyncio.run(_aresolve_scoped_twice())
    assert first is second


async def _aresolve_scoped_without_scope() -> None:
    """Coroutine helper covered by :func:`test_aresolve_scoped_without_scope_raises`."""
    graph = DependencyGraph()
    graph.register(
        Binding(
            token=_Clock,
            async_factory=_async_clock_factory,
            lifecycle=Lifecycle.SCOPED,
        )
    )
    await Resolver(graph).aresolve(_Clock)


def test_aresolve_scoped_without_scope_raises_scope_error() -> None:
    """An async SCOPED resolve without an open scope also raises ScopeError."""
    with pytest.raises(ScopeError, match="SCOPED lifecycle but no scope"):
        asyncio.run(_aresolve_scoped_without_scope())


async def _aresolve_scoped_registers_aclose() -> int:
    """Helper for the async SCOPED + aclose registration test.

    Also drives ``aclose`` on the registered target so the
    stand-in's body is covered (same pattern as the singleton
    suite).
    """
    graph = DependencyGraph()
    graph.register(
        Binding(
            token=_AsyncCloseable,
            factory=_AsyncCloseable,
            lifecycle=Lifecycle.SCOPED,
        )
    )
    resolver = Resolver(graph)
    async with alifetime_scope() as scope:
        instance = resolver.resolve(_AsyncCloseable)
        assert scope.teardowns() == (instance,)
        await instance.aclose()
        return instance.aclose_calls


def test_aresolve_scoped_registers_async_closeable() -> None:
    """An AsyncCloseable SCOPED instance lands in the scope's teardown list."""
    assert asyncio.run(_aresolve_scoped_registers_aclose()) == 1


# --- TRANSIENT and SINGLETON regression with scope --------------------------


def test_transient_resolution_ignores_active_scope() -> None:
    """TRANSIENT bindings build a fresh instance regardless of any open scope."""
    graph = DependencyGraph()
    graph.register(Binding(token=_Clock, factory=_Clock, lifecycle=Lifecycle.TRANSIENT))
    resolver = Resolver(graph)
    with lifetime_scope() as scope:
        first = resolver.resolve(_Clock)
        second = resolver.resolve(_Clock)
    assert first is not second
    assert scope.teardowns() == ()


def test_singleton_resolution_ignores_active_scope() -> None:
    """SINGLETON cache lives on the resolver, not on the open scope."""
    graph = DependencyGraph()
    graph.register(
        Binding(token=_Closeable, factory=_Closeable, lifecycle=Lifecycle.SINGLETON)
    )
    resolver = Resolver(graph)
    with lifetime_scope() as scope:
        first = resolver.resolve(_Closeable)
    with lifetime_scope() as second_scope:
        second = resolver.resolve(_Closeable)
    # Same instance across scopes (SINGLETON wins over scope boundary).
    assert first is second
    # And the teardown is registered on the resolver, not on either scope.
    assert resolver.teardowns() == (first,)
    assert scope.teardowns() == ()
    assert second_scope.teardowns() == ()
