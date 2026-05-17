# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Resolver - turns registered tokens into instances.

The :class:`Resolver` is the smallest unit that can answer
"what instance does this token map to?". It ties together three
components introduced in earlier commits:

- :class:`DependencyGraph` - the registry of bindings;
- :class:`ResolutionContext` - the in-flight token stack;
- :func:`guarded_resolving` - the cycle detector.

This commit implements the **transient** lifecycle: every call
to :meth:`Resolver.resolve` (or :meth:`Resolver.aresolve`)
returns a freshly built instance. Singleton caching (3.6),
scoped lifetimes (3.7) and teardown propagation (3.9) plug into
the same dispatch entry point in later commits.

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
"""

from collections.abc import Callable
from typing import Any, cast

from tripack_contracts import DependencyToken, Lifecycle, ResolutionError
from tripack_runtime.binding import Binding
from tripack_runtime.context import (
    ResolutionContext,
    aresolution_scope,
    current_context,
    resolution_scope,
)
from tripack_runtime.cycles import aguarded_resolving, guarded_resolving
from tripack_runtime.graph import DependencyGraph


class Resolver:
    """Resolve registered tokens through a :class:`DependencyGraph`.

    The resolver holds no per-call state beyond the graph
    reference. Cycle detection is enforced via
    :func:`guarded_resolving` and the in-flight stack lives on
    the active :class:`ResolutionContext`.

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

    __slots__ = ("_graph",)

    def __init__(self, graph: DependencyGraph) -> None:
        """Bind the resolver to ``graph``; no other state is kept."""
        self._graph = graph

    def resolve[T](self, token: type[T]) -> T:
        """Return a fresh instance for ``token`` via its sync factory.

        Inherits the currently active
        :class:`ResolutionContext` if one exists (so a factory
        that calls back into ``resolve`` participates in the
        same cycle-detection stack); otherwise opens a scope for
        the duration of the call.

        Raises:
            ResolutionError: when ``token`` is unknown or when
                the binding is async-only - use :meth:`aresolve`
                to drive async factories.
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
        directly; an ``async_factory`` is awaited. Each
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
        with guarded_resolving(ctx, token):
            return self._invoke_sync(binding)

    async def _aresolve_in(self, ctx: ResolutionContext, token: DependencyToken) -> Any:
        binding = self._graph.lookup(token)
        async with aguarded_resolving(ctx, token):
            return await self._invoke_async(binding)

    def _invoke_sync(self, binding: Binding) -> Any:
        if binding.factory is None:
            raise ResolutionError(
                f"Binding for token {binding.token!r} is async-only; "
                "use aresolve() to drive it."
            )
        if binding.lifecycle != Lifecycle.TRANSIENT:
            raise NotImplementedError(
                f"Lifecycle {binding.lifecycle} not yet supported by Resolver."
            )
        return binding.factory()

    async def _invoke_async(self, binding: Binding) -> Any:
        if binding.lifecycle != Lifecycle.TRANSIENT:
            raise NotImplementedError(
                f"Lifecycle {binding.lifecycle} not yet supported by Resolver."
            )
        async_factory = binding.async_factory
        if async_factory is not None:
            return await async_factory()
        # Binding.__post_init__ guarantees factory is set when async_factory is None.
        factory = cast("Callable[[], Any]", binding.factory)
        return factory()
