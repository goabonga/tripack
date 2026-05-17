# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Unit tests for the transient resolver."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from tripack_contracts import CircularDependencyError, ResolutionError
from tripack_contracts import Resolver as ResolverProtocol
from tripack_runtime import (
    Binding,
    DependencyGraph,
    Resolver,
    aresolution_scope,
    current_context,
    resolution_scope,
)


class _Clock:
    """Framework-neutral token, used both as token and as factory."""


class _Cache:
    """A second framework-neutral token, used for cycle tests."""


async def _async_clock_factory() -> _Clock:
    """Module-level async factory reused across the rejection and async tests.

    Extracted so the rejection test (where the factory body never
    runs) does not leave the body uncovered: the same callable is
    also exercised through ``aresolve`` below.
    """
    return _Clock()


# --- sync path ------------------------------------------------------------


def test_resolve_returns_an_instance_built_by_the_factory() -> None:
    """The factory's return value is what ``resolve`` hands back."""
    graph = DependencyGraph()
    graph.register(Binding(token=_Clock, factory=_Clock))
    resolver = Resolver(graph)
    instance = resolver.resolve(_Clock)
    assert isinstance(instance, _Clock)


def test_resolve_returns_a_fresh_instance_every_call() -> None:
    """Transient lifecycle: no caching, two calls -> two instances."""
    graph = DependencyGraph()
    graph.register(Binding(token=_Clock, factory=_Clock))
    resolver = Resolver(graph)
    first = resolver.resolve(_Clock)
    second = resolver.resolve(_Clock)
    assert first is not second


def test_resolve_raises_resolution_error_for_an_unknown_token() -> None:
    """An unbound token surfaces as :class:`ResolutionError`."""
    resolver = Resolver(DependencyGraph())
    with pytest.raises(ResolutionError, match="No binding registered"):
        resolver.resolve(_Clock)


def test_resolve_rejects_async_only_bindings() -> None:
    """A binding whose only factory is async cannot be driven by ``resolve``."""
    graph = DependencyGraph()
    graph.register(Binding(token=_Clock, async_factory=_async_clock_factory))
    resolver = Resolver(graph)
    with pytest.raises(ResolutionError, match="async-only"):
        resolver.resolve(_Clock)


def test_resolve_detects_cycles_across_factory_recursion() -> None:
    """A factory that calls back into ``resolve`` is in the cycle stack."""
    graph = DependencyGraph()
    resolver: Resolver

    def _make_clock() -> Any:
        resolver.resolve(_Cache)

    def _make_cache() -> Any:
        resolver.resolve(_Clock)

    graph.register(Binding(token=_Clock, factory=_make_clock))
    graph.register(Binding(token=_Cache, factory=_make_cache))
    resolver = Resolver(graph)
    with pytest.raises(CircularDependencyError) as exc_info:
        resolver.resolve(_Clock)
    assert exc_info.value.cycle == (_Clock, _Cache, _Clock)


def test_resolve_inherits_an_active_resolution_context() -> None:
    """When a scope is already open, ``resolve`` reuses it."""
    captured: list[Any] = []

    def _factory() -> _Clock:
        captured.append(current_context())
        return _Clock()

    graph = DependencyGraph()
    graph.register(Binding(token=_Clock, factory=_factory))
    resolver = Resolver(graph)
    with resolution_scope() as outer:
        resolver.resolve(_Clock)
    assert captured == [outer]


def test_resolve_opens_its_own_scope_when_none_is_active() -> None:
    """Without an outer scope, ``resolve`` creates one for the call."""
    captured: list[Any] = []

    def _factory() -> _Clock:
        captured.append(current_context())
        return _Clock()

    graph = DependencyGraph()
    graph.register(Binding(token=_Clock, factory=_factory))
    resolver = Resolver(graph)
    assert current_context() is None
    resolver.resolve(_Clock)
    assert captured[0] is not None
    # Scope was torn down on exit; nothing leaked.
    assert current_context() is None


def test_resolver_uses_slots_not_dict() -> None:
    """``__slots__`` keeps the resolver instance free of per-instance dict."""
    resolver = Resolver(DependencyGraph())
    assert not hasattr(resolver, "__dict__")


def test_resolver_satisfies_the_contracts_resolver_protocol() -> None:
    """The runtime ``Resolver`` is a structural ``Resolver`` Protocol impl.

    The annotation itself is the mypy assertion under strict mode;
    the runtime check keeps the test live. The contracts
    ``AsyncResolver`` Protocol is intentionally NOT claimed by the
    runtime resolver: it defines ``async def resolve``, which would
    collide with the sync ``resolve`` above. The runtime offers
    ``aresolve`` as a parallel async entry point instead.
    """
    resolver: ResolverProtocol = Resolver(DependencyGraph())
    assert callable(resolver.resolve)


# --- async path -----------------------------------------------------------


async def _aresolve_sync_factory() -> _Clock:
    """Coroutine helper covered by :func:`test_aresolve_drives_a_sync_factory`."""
    graph = DependencyGraph()
    graph.register(Binding(token=_Clock, factory=_Clock))
    return await Resolver(graph).aresolve(_Clock)


def test_aresolve_drives_a_sync_factory() -> None:
    """``aresolve`` handles plain sync factories without awaiting them."""
    instance = asyncio.run(_aresolve_sync_factory())
    assert isinstance(instance, _Clock)


async def _aresolve_async_factory() -> _Clock:
    """Coroutine helper covered by :func:`test_aresolve_drives_an_async_factory`."""
    graph = DependencyGraph()
    graph.register(Binding(token=_Clock, async_factory=_async_clock_factory))
    return await Resolver(graph).aresolve(_Clock)


def test_aresolve_drives_an_async_factory() -> None:
    """``aresolve`` awaits an ``async_factory`` and returns its result."""
    instance = asyncio.run(_aresolve_async_factory())
    assert isinstance(instance, _Clock)


async def _aresolve_two_instances() -> tuple[_Clock, _Clock]:
    """Coroutine helper covered by :func:`test_aresolve_returns_fresh_instances`."""
    graph = DependencyGraph()
    graph.register(Binding(token=_Clock, factory=_Clock))
    resolver = Resolver(graph)
    a = await resolver.aresolve(_Clock)
    b = await resolver.aresolve(_Clock)
    return a, b


def test_aresolve_returns_fresh_instances() -> None:
    """Transient lifetime on the async path: no caching across calls."""
    a, b = asyncio.run(_aresolve_two_instances())
    assert a is not b


async def _aresolve_inherits_async_context() -> tuple[Any, Any]:
    """Coroutine helper covered by :func:`test_aresolve_inherits_an_active_context`."""
    captured: list[Any] = []

    async def _factory() -> _Clock:
        captured.append(current_context())
        return _Clock()

    graph = DependencyGraph()
    graph.register(Binding(token=_Clock, async_factory=_factory))
    resolver = Resolver(graph)
    async with aresolution_scope() as outer:
        await resolver.aresolve(_Clock)
    return captured[0], outer


def test_aresolve_inherits_an_active_context() -> None:
    """An open async scope is reused by ``aresolve``."""
    seen, outer = asyncio.run(_aresolve_inherits_async_context())
    assert seen is outer


async def _aresolve_opens_own_scope() -> tuple[Any, Any]:
    """Coroutine helper covered by :func:`test_aresolve_opens_its_own_scope`."""
    captured: list[Any] = []

    async def _factory() -> _Clock:
        captured.append(current_context())
        return _Clock()

    graph = DependencyGraph()
    graph.register(Binding(token=_Clock, async_factory=_factory))
    resolver = Resolver(graph)
    assert current_context() is None
    await resolver.aresolve(_Clock)
    return captured[0], current_context()


def test_aresolve_opens_its_own_scope_when_none_is_active() -> None:
    """Without an outer async scope, ``aresolve`` creates one for the call."""
    seen, leftover = asyncio.run(_aresolve_opens_own_scope())
    assert seen is not None
    assert leftover is None


async def _aresolve_cycle_trigger() -> None:
    """Trigger coroutine for the async cycle test - always raises."""
    graph = DependencyGraph()
    resolver: Resolver

    async def _make_clock() -> Any:
        await resolver.aresolve(_Cache)

    async def _make_cache() -> Any:
        await resolver.aresolve(_Clock)

    graph.register(Binding(token=_Clock, async_factory=_make_clock))
    graph.register(Binding(token=_Cache, async_factory=_make_cache))
    resolver = Resolver(graph)
    await resolver.aresolve(_Clock)


def test_aresolve_detects_cycles() -> None:
    """A cycle across async factories raises :class:`CircularDependencyError`."""
    with pytest.raises(CircularDependencyError) as exc_info:
        asyncio.run(_aresolve_cycle_trigger())
    assert exc_info.value.cycle == (_Clock, _Cache, _Clock)
