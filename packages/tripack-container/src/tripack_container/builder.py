# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Container builder - fluent factory for sealed :class:`Container` instances.

The :class:`ContainerBuilder` lets users assemble a wiring in
several ``bind`` calls (possibly across modules in 4.4, helpers
in 4.5, or config loaders in 4.9-4.11) and then materialise it
through :meth:`build`. The returned :class:`Container` is
**sealed**: further :meth:`Container.bind` calls raise
:class:`tripack_contracts.BindingError`.

The builder itself stays mutable, so a single instance can
produce many independent containers - each ``build`` snapshots
the current bindings into a fresh
:class:`tripack_runtime.DependencyGraph`, hands it to the new
container, and seals the latter. Subsequent ``bind`` calls on
the builder do not affect already-built containers.

```python
builder = ContainerBuilder()
container = (
    builder
    .bind(Clock, make_clock, lifecycle=Lifecycle.SINGLETON)
    .bind(Cache, make_cache, lifecycle=Lifecycle.SCOPED)
    .build()
)
clock = container.resolve(Clock)
```
"""

from collections.abc import Awaitable, Callable
from typing import Self, overload

from tripack_container.container import Container, _make_binding
from tripack_container.module import Module
from tripack_contracts import Lifecycle
from tripack_runtime import DependencyGraph


class ContainerBuilder:
    """Fluent builder that produces sealed :class:`Container` instances."""

    __slots__ = ("_graph", "_installed_modules")

    def __init__(self) -> None:
        """Start with an empty :class:`DependencyGraph` and no installed modules."""
        self._graph = DependencyGraph()
        # Track installed modules by ``id()`` so a second
        # ``install(same_instance)`` is a no-op without
        # requiring modules to implement equality / hashing.
        self._installed_modules: set[int] = set()

    # Async overload first: the broader ``Callable[..., T]`` would
    # otherwise mask ``Callable[..., Awaitable[T]]`` (overload-cannot-match).
    @overload
    def bind[T](
        self,
        token: type[T],
        factory: Callable[..., Awaitable[T]],
        *,
        lifecycle: Lifecycle = ...,
        auto_inject: bool = ...,
    ) -> Self: ...

    @overload
    def bind[T](
        self,
        token: type[T],
        factory: Callable[..., T],
        *,
        lifecycle: Lifecycle = ...,
        auto_inject: bool = ...,
    ) -> Self: ...

    def bind[T](
        self,
        token: type[T],
        factory: Callable[..., T] | Callable[..., Awaitable[T]],
        *,
        lifecycle: Lifecycle = Lifecycle.TRANSIENT,
        auto_inject: bool = False,
    ) -> Self:
        """Register a binding and return ``self`` for fluent chaining.

        Same auto-detection and idempotence semantics as
        :meth:`Container.bind`. The return value is the builder
        itself, so calls can be chained:

        .. code-block:: python

            builder.bind(Clock, make_clock).bind(Cache, make_cache)
        """
        binding = _make_binding(
            token,
            factory,
            lifecycle=lifecycle,
            auto_inject=auto_inject,
        )
        self._graph.register(binding)
        return self

    def install(self, module: Module) -> Self:
        """Apply ``module`` to this builder and return ``self`` for chaining.

        Idempotent per-instance: calling ``install`` twice with
        the same :class:`Module` object is a no-op on the second
        call (no double-registration, no double-side-effect).
        Tracking is by :func:`id`, so two distinct instances of
        the same module class are treated as separate modules
        and both run - the graph's own idempotent
        ``register`` then deduplicates the actual bindings if
        they happen to match.

        Composition is recursive: a module's ``register`` can
        call ``builder.install(other_module)`` to pull in a
        sub-module. The per-instance guard prevents the
        diamond-install pitfall (two modules each installing a
        common dependency module).
        """
        if id(module) in self._installed_modules:
            return self
        self._installed_modules.add(id(module))
        module.register(self)
        return self

    def build(self) -> Container:
        """Materialise the accumulated bindings into a sealed container.

        Each call snapshots the current bindings into a fresh
        :class:`DependencyGraph`, hands it to a new
        :class:`Container`, and seals the latter. Two successive
        ``build`` calls therefore return two independent
        containers that are equivalent in registered bindings
        but isolated in their resolver state (singletons cached
        in one are not visible from the other).
        """
        snapshot = DependencyGraph()
        for binding in self._graph.bindings():
            snapshot.register(binding)
        container = Container(graph=snapshot)
        container._seal()
        return container
