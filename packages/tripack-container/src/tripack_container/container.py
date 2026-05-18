# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Container - the high-level user-facing IoC API.

The :class:`Container` is the front door of ``tripack-container``.
Consumers program against it; the runtime layer
(:class:`tripack_runtime.Resolver`, :class:`tripack_runtime.Scope`)
stays an implementation detail visible only when extending the
framework.

This commit (4.2) adds the binding API: a typed
:meth:`Container.bind` method with separate overloads for sync
and async factories. The implementation auto-detects which
shape it received via :func:`inspect.iscoroutinefunction` and
hands the right :class:`tripack_runtime.Binding` slot to the
graph. The ``auto_inject`` keyword is accepted now (stored on
the binding) but the actual constructor-injection wrapping
lands in 4.6.
"""

import inspect
from collections.abc import Awaitable, Callable
from typing import Any, cast, overload

from tripack_contracts import Lifecycle
from tripack_runtime import Binding, DependencyGraph, Resolver


class Container:
    """High-level IoC container backed by a :class:`Resolver`.

    Wraps a private :class:`DependencyGraph` and the matching
    :class:`Resolver`; the graph is empty at construction time
    and is populated through :meth:`bind`.
    """

    __slots__ = ("_graph", "_resolver")

    def __init__(self) -> None:
        """Create an empty container.

        Builds an empty :class:`DependencyGraph` and the
        matching :class:`Resolver`. No bindings are registered
        yet, so any ``resolve`` call raises
        :class:`tripack_contracts.ResolutionError` until
        :meth:`bind` is called.
        """
        self._graph = DependencyGraph()
        self._resolver = Resolver(self._graph)

    # Async overload first: ``Callable[..., T]`` would otherwise mask
    # ``Callable[..., Awaitable[T]]`` since the broader return type
    # matches any return shape (mypy overload-cannot-match).
    @overload
    def bind[T](
        self,
        token: type[T],
        factory: Callable[..., Awaitable[T]],
        *,
        lifecycle: Lifecycle = ...,
        auto_inject: bool = ...,
    ) -> None: ...

    @overload
    def bind[T](
        self,
        token: type[T],
        factory: Callable[..., T],
        *,
        lifecycle: Lifecycle = ...,
        auto_inject: bool = ...,
    ) -> None: ...

    def bind[T](
        self,
        token: type[T],
        factory: Callable[..., T] | Callable[..., Awaitable[T]],
        *,
        lifecycle: Lifecycle = Lifecycle.TRANSIENT,
        auto_inject: bool = False,
    ) -> None:
        """Register ``factory`` for ``token`` under the given lifecycle.

        Auto-detects whether ``factory`` is a sync callable or an
        ``async def`` (via :func:`inspect.iscoroutinefunction`)
        and routes it to the matching
        :class:`tripack_runtime.Binding` slot. The keyword form
        of the call keeps the call site self-documenting:

        .. code-block:: python

            container.bind(Clock, make_clock, lifecycle=Lifecycle.SINGLETON)
            container.bind(Cache, async_make_cache, lifecycle=Lifecycle.SCOPED)

        Re-binding the same ``(token, factory, lifecycle,
        auto_inject)`` tuple is a no-op (the underlying graph
        treats structurally identical bindings as idempotent);
        any difference on those fields raises
        :class:`tripack_contracts.BindingError`.

        The ``auto_inject`` flag is stored on the binding now;
        the actual constructor-injection wrapping is added in
        4.6.
        """
        if inspect.iscoroutinefunction(factory):
            binding = Binding(
                token=token,
                async_factory=cast("Callable[..., Awaitable[Any]]", factory),
                lifecycle=lifecycle,
                auto_inject=auto_inject,
            )
        else:
            binding = Binding(
                token=token,
                factory=cast("Callable[..., Any]", factory),
                lifecycle=lifecycle,
                auto_inject=auto_inject,
            )
        self._graph.register(binding)

    def resolve[T](self, token: type[T]) -> T:
        """Return an instance for ``token`` via the underlying resolver.

        Delegates to :meth:`tripack_runtime.Resolver.resolve`
        and inherits its full contract: lifecycle dispatch,
        cycle detection, sync-factory only (use :meth:`aresolve`
        for async factories).
        """
        return self._resolver.resolve(token)

    async def aresolve[T](self, token: type[T]) -> T:
        """Asynchronous counterpart of :meth:`resolve`.

        Delegates to :meth:`tripack_runtime.Resolver.aresolve`.
        Drives both sync and async factories.
        """
        return await self._resolver.aresolve(token)
