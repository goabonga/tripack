# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Resolver - turns registered tokens into instances.

The :class:`Resolver` is the smallest unit that can answer
"what instance does this token map to?". It ties together four
components introduced in earlier commits:

- :class:`DependencyGraph` - the registry of bindings;
- :class:`ResolutionContext` - the in-flight token stack;
- :func:`guarded_resolving` - the cycle detector;
- :class:`Scope` (3.7) - the per-scope cache + teardown list.

Lifecycles are dispatched centrally in :meth:`_resolve_in` /
:meth:`_aresolve_in`:

- ``TRANSIENT`` - a fresh instance is built on every call; no
  cache, no teardown registration.
- ``SINGLETON`` - the first call builds the instance and caches
  it on the resolver; subsequent calls return the cached one.
  Closeable / AsyncCloseable instances land in the resolver-
  level teardown registry.
- ``SCOPED`` - requires an active :class:`Scope`; the first
  call within a given scope builds the instance and caches it
  on the scope; subsequent calls within the same scope return
  the cached one. Closeable instances land in the scope's
  teardown registry. Resolving a SCOPED token without an active
  scope raises :class:`ScopeError`.

Sync and async paths are mirrored:

- :meth:`resolve` drives sync factories only. An async-only
  binding raises :class:`ResolutionError`.
- :meth:`aresolve` drives both shapes: a sync ``factory`` is
  called directly, an ``async_factory`` is awaited.

Both paths inherit the currently active
:class:`ResolutionContext` if one is open (so a factory that
calls back into the resolver participates in the same cycle-
detection stack); otherwise they open their own scope for the
duration of the call.

Teardown is registered, not yet propagated. The runtime
collects :class:`Closeable` / :class:`AsyncCloseable` instances
on either the resolver (singletons) or the active scope (SCOPED
bindings); 3.9 wires up the actual ``close`` / ``aclose``
invocation at scope or container exit.
"""

from collections.abc import Callable
from typing import Any, cast

from tripack_contracts import (
    AsyncCloseable,
    Closeable,
    DependencyToken,
    Lifecycle,
    ResolutionError,
    ScopeError,
)
from tripack_runtime.binding import Binding
from tripack_runtime.context import (
    ResolutionContext,
    aresolution_scope,
    current_context,
    resolution_scope,
)
from tripack_runtime.cycles import aguarded_resolving, guarded_resolving
from tripack_runtime.graph import DependencyGraph
from tripack_runtime.scope import (
    _MISSING,
    Scope,
    current_scope,
    is_teardown_target,
)


class Resolver:
    """Resolve registered tokens through a :class:`DependencyGraph`.

    Holds three pieces of state:

    - ``_graph`` - the binding registry (read at lookup time);
    - ``_singletons`` - the singleton cache, keyed by token;
    - ``_teardowns`` - the ordered list of cached SINGLETON
      instances that satisfy :class:`Closeable` /
      :class:`AsyncCloseable`. SCOPED teardowns live on each
      :class:`Scope` instead.

    Cycle detection is enforced via :func:`guarded_resolving`
    and the in-flight stack lives on the active
    :class:`ResolutionContext`. The active :class:`Scope` for
    SCOPED dispatch is read from :func:`current_scope`.

    Implements the :class:`tripack_contracts.Resolver` Protocol
    structurally on the sync side. The async side is exposed
    through :meth:`aresolve` rather than an ``async def resolve``,
    so the runtime resolver does NOT satisfy
    :class:`tripack_contracts.AsyncResolver` (whose contract is
    ``async def resolve`` and would collide with the sync method
    name on the same class). Consumers wanting the awaitable
    Protocol surface should expose ``aresolve`` under a separate
    adapter object.
    """

    __slots__ = ("_graph", "_singletons", "_teardowns")

    def __init__(self, graph: DependencyGraph) -> None:
        """Bind the resolver to ``graph``; initialise empty caches."""
        self._graph = graph
        self._singletons: dict[DependencyToken, Any] = {}
        self._teardowns: list[Closeable | AsyncCloseable] = []

    def teardowns(self) -> tuple[Closeable | AsyncCloseable, ...]:
        """Snapshot of SINGLETON teardown targets in registration order.

        Returned as a tuple so callers cannot mutate the
        underlying list. Insertion order matches construction
        order; the eventual teardown propagation (3.9) will
        iterate in reverse so dependents close before what they
        depend on. SCOPED teardowns are exposed on each
        :class:`Scope` separately and are not included here.
        """
        return tuple(self._teardowns)

    def resolve[T](self, token: type[T]) -> T:
        """Return an instance for ``token`` via its sync factory.

        Honors the binding's lifecycle: ``TRANSIENT`` builds a
        fresh instance every call, ``SINGLETON`` caches the
        first one on the resolver, ``SCOPED`` caches the first
        one on the active :class:`Scope`.

        Inherits the currently active
        :class:`ResolutionContext` if one exists (so a factory
        that calls back into ``resolve`` participates in the
        same cycle-detection stack); otherwise opens a scope for
        the duration of the call.

        Raises:
            ResolutionError: when ``token`` is unknown, or when
                the binding is async-only AND not yet cached -
                use :meth:`aresolve` to drive async factories.
            ScopeError: when the binding is SCOPED and no scope
                is currently active.
            CircularDependencyError: when the factory recursion
                re-enters a token already on the stack.
        """
        ctx = current_context()
        if ctx is None:
            with resolution_scope() as ctx:
                return cast("T", self._resolve_in(ctx, token))
        return cast("T", self._resolve_in(ctx, token))

    async def aresolve[T](self, token: type[T]) -> T:
        """Asynchronous counterpart of :meth:`resolve`.

        Drives both factory shapes: a sync ``factory`` is called
        directly; an ``async_factory`` is awaited. Honors the
        same lifecycle dispatch as :meth:`resolve`. Each
        :class:`asyncio.Task` started inside the scope inherits
        its own copy of the resolution context, so concurrent
        :func:`asyncio.gather` calls do not share stacks.

        Raises:
            ResolutionError: when ``token`` is unknown.
            ScopeError: when the binding is SCOPED and no scope
                is currently active.
            CircularDependencyError: when the factory recursion
                re-enters a token already on the stack.
        """
        ctx = current_context()
        if ctx is None:
            async with aresolution_scope() as ctx:
                return cast("T", await self._aresolve_in(ctx, token))
        return cast("T", await self._aresolve_in(ctx, token))

    def _resolve_in(self, ctx: ResolutionContext, token: DependencyToken) -> Any:
        binding = self._graph.lookup(token)
        cached = self._lookup_cached(binding, token)
        if cached is not _MISSING:
            return cached
        with guarded_resolving(ctx, token):
            instance = self._invoke_sync(binding)
        self._cache_if_applicable(binding, token, instance)
        return instance

    async def _aresolve_in(self, ctx: ResolutionContext, token: DependencyToken) -> Any:
        binding = self._graph.lookup(token)
        cached = self._lookup_cached(binding, token)
        if cached is not _MISSING:
            return cached
        async with aguarded_resolving(ctx, token):
            instance = await self._invoke_async(binding)
        self._cache_if_applicable(binding, token, instance)
        return instance

    def _lookup_cached(self, binding: Binding, token: DependencyToken) -> Any:
        lifecycle = binding.lifecycle
        if lifecycle == Lifecycle.SINGLETON:
            return self._singletons.get(token, _MISSING)
        if lifecycle == Lifecycle.SCOPED:
            scope = current_scope()
            if scope is None:
                raise ScopeError(
                    f"Token {binding.token!r} has SCOPED lifecycle but no "
                    "scope is active; open one with lifetime_scope() or "
                    "alifetime_scope() before resolving."
                )
            return scope.lookup(token)
        return _MISSING

    def _cache_if_applicable(
        self, binding: Binding, token: DependencyToken, instance: Any
    ) -> None:
        lifecycle = binding.lifecycle
        if lifecycle == Lifecycle.SINGLETON:
            self._singletons[token] = instance
            self._register_teardown(instance)
        elif lifecycle == Lifecycle.SCOPED:
            # _lookup_cached raised ScopeError if no scope was active, so
            # current_scope() is guaranteed non-None here as long as the
            # caller did not close the scope mid-resolution. A ``cast``
            # narrows the type for mypy without the runtime ``assert``
            # bandit flags as B101 (asserts are stripped under
            # ``python -O``, so they are not a robust runtime check).
            scope = cast("Scope", current_scope())
            scope.remember(token, instance)

    def _register_teardown(self, instance: Any) -> None:
        if is_teardown_target(instance):
            self._teardowns.append(instance)

    def _invoke_sync(self, binding: Binding) -> Any:
        if binding.factory is None:
            raise ResolutionError(
                f"Binding for token {binding.token!r} is async-only; "
                "use aresolve() to drive it."
            )
        return binding.factory()

    async def _invoke_async(self, binding: Binding) -> Any:
        async_factory = binding.async_factory
        if async_factory is not None:
            return await async_factory()
        # Binding.__post_init__ guarantees factory is set when async_factory is None.
        factory = cast("Callable[[], Any]", binding.factory)
        return factory()
