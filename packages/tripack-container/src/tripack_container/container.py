# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Container - the high-level user-facing IoC API.

The :class:`Container` is the front door of ``tripack-container``.
Consumers program against it; the runtime layer
(:class:`tripack_runtime.Resolver`, :class:`tripack_runtime.Scope`)
stays an implementation detail visible only when extending the
framework.

This commit ships the skeleton: a container with sync and async
``resolve`` entry points and an empty :class:`DependencyGraph`
under the hood. Subsequent commits in this phase add the
binding API (4.2), the builder (4.3), modules (4.4), provider
helpers (4.5), constructor injection (4.6), scopes (4.7),
teardown (4.8) and the configuration loaders (4.9-4.11).
"""

from tripack_runtime import DependencyGraph, Resolver


class Container:
    """High-level IoC container backed by a :class:`Resolver`.

    Wraps a private :class:`DependencyGraph` and the matching
    :class:`Resolver`; the graph is empty at construction time.
    Bindings are added through the API introduced in 4.2.
    """

    __slots__ = ("_graph", "_resolver")

    def __init__(self) -> None:
        """Create an empty container.

        Builds an empty :class:`DependencyGraph` and the
        matching :class:`Resolver`. No bindings are registered
        yet, so any ``resolve`` call raises
        :class:`tripack_contracts.ResolutionError` until the
        binding API (4.2) is wired up.
        """
        self._graph = DependencyGraph()
        self._resolver = Resolver(self._graph)

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
