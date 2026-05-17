# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Resolver - turns registered tokens into instances.

The :class:`Resolver` is the smallest unit that can answer
"what instance does this token map to?". It ties together three
components introduced in earlier commits:

- :class:`DependencyGraph` - the registry of bindings;
- :class:`ResolutionContext` - the in-flight token stack;
- :func:`guarded_resolving` - the cycle detector.

Lifecycles are dispatched centrally in :meth:`_resolve_in` /
:meth:`_aresolve_in`:

- ``TRANSIENT`` - a fresh instance is built on every call; no
  cache, no teardown registration.
- ``SINGLETON`` (this commit) - the first call builds the
  instance, subsequent calls return the cached one. Closeable /
  AsyncCloseable instances are registered for later teardown.
- ``SCOPED`` - raises :class:`NotImplementedError`; wired up in
  3.7.

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

Singleton teardown is registered, not yet propagated. The
runtime collects :class:`Closeable` / :class:`AsyncCloseable`
instances in insertion order via :meth:`teardowns`; 3.9 wires
up the actual ``close`` / ``aclose`` invocation at scope or
container exit.
"""

from collections.abc import Callable
from typing import Any, Final, cast

from tripack_contracts import (
    AsyncCloseable,
    Closeable,
    DependencyToken,
    Lifecycle,
    ResolutionError,
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

_MISSING: Final[Any] = object()


class Resolver:
    """Resolve registered tokens through a :class:`DependencyGraph`.

    Holds three pieces of state:

    - ``_graph`` - the binding registry (read at lookup time);
    - ``_singletons`` - the singleton cache, keyed by token;
    - ``_teardowns`` - the ordered list of cached instances that
      satisfy :class:`Closeable` / :class:`AsyncCloseable`.

    Cycle detection is enforced via :func:`guarded_resolving`
    and the in-flight stack lives on the active
    :class:`ResolutionContext`.

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
        """Snapshot of registered teardown targets in registration order.

        Returned as a tuple so callers cannot mutate the
        underlying list. Insertion order matches construction
        order; the eventual teardown propagation (3.9) will
        iterate in reverse so dependents are closed before the
        services they depend on.
        """
        return tuple(self._teardowns)

    def resolve[T](self, token: type[T]) -> T:
        """Return an instance for ``token`` via its sync factory.

        Honors the binding's lifecycle: ``TRANSIENT`` builds a
        fresh instance every call, ``SINGLETON`` caches the
        first one and returns it on subsequent calls.

        Inherits the currently active
        :class:`ResolutionContext` if one exists (so a factory
        that calls back into ``resolve`` participates in the
        same cycle-detection stack); otherwise opens a scope for
        the duration of the call.

        Raises:
            ResolutionError: when ``token`` is unknown, or when
                the binding is async-only AND not yet cached -
                use :meth:`aresolve` to drive async factories.
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
        self._guard_supported_lifecycle(binding)
        with guarded_resolving(ctx, token):
            instance = self._invoke_sync(binding)
        self._cache_if_applicable(binding, token, instance)
        return instance

    async def _aresolve_in(self, ctx: ResolutionContext, token: DependencyToken) -> Any:
        binding = self._graph.lookup(token)
        cached = self._lookup_cached(binding, token)
        if cached is not _MISSING:
            return cached
        self._guard_supported_lifecycle(binding)
        async with aguarded_resolving(ctx, token):
            instance = await self._invoke_async(binding)
        self._cache_if_applicable(binding, token, instance)
        return instance

    def _lookup_cached(self, binding: Binding, token: DependencyToken) -> Any:
        if binding.lifecycle == Lifecycle.SINGLETON:
            return self._singletons.get(token, _MISSING)
        return _MISSING

    def _guard_supported_lifecycle(self, binding: Binding) -> None:
        if binding.lifecycle not in (Lifecycle.TRANSIENT, Lifecycle.SINGLETON):
            raise NotImplementedError(
                f"Lifecycle {binding.lifecycle} not yet supported by Resolver."
            )

    def _cache_if_applicable(
        self, binding: Binding, token: DependencyToken, instance: Any
    ) -> None:
        if binding.lifecycle == Lifecycle.SINGLETON:
            self._singletons[token] = instance
            self._register_teardown(instance)

    def _register_teardown(self, instance: Any) -> None:
        # Duck-typing rather than ``isinstance`` because the contracts
        # Protocols are not @runtime_checkable; a class that exposes
        # the right method shape qualifies, matching the spirit of
        # structural typing.
        has_close = callable(getattr(instance, "close", None))
        has_aclose = callable(getattr(instance, "aclose", None))
        if has_close or has_aclose:
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
