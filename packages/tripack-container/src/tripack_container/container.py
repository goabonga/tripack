# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Container - the high-level user-facing IoC API.

The :class:`Container` is the front door of ``tripack-container``.
Consumers program against it; the runtime layer
(:class:`tripack_runtime.Resolver`, :class:`tripack_runtime.Scope`)
stays an implementation detail visible only when extending the
framework.

This commit (4.3) adds the sealing semantics: a Container
created by :class:`ContainerBuilder.build` cannot accept any
further :meth:`bind` call. The default constructor still
creates an unfrozen Container (used by tests and by ad-hoc
imperative wiring); the freezer is reached only through the
builder. The shared binding helper :func:`_make_binding` is
factored at the module level so both ``Container.bind`` and
``ContainerBuilder.bind`` produce a uniform
:class:`tripack_runtime.Binding`.
"""

import inspect
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from contextlib import asynccontextmanager, contextmanager
from typing import Any, cast, overload

from tripack_container.providers import INJECT_ATTR, LIFECYCLE_ATTR
from tripack_contracts import BindingError, Lifecycle, ResolutionError
from tripack_runtime import (
    Binding,
    DependencyGraph,
    Resolver,
    Scope,
    alifetime_scope,
    lifetime_scope,
)


def _validate_injectable_signature(
    factory: Callable[..., Any] | Callable[..., Awaitable[Any]],
) -> list[inspect.Parameter]:
    """Inspect ``factory``'s signature and assert it is injectable.

    Returns the ordered list of parameters that the
    injection-wrap helper later iterates at resolve time, with
    each parameter's annotation **resolved** so callers do not
    need to handle ``from __future__ import annotations``
    stringified forms. A parameter without an annotation AND
    without a default value raises
    :class:`tripack_contracts.BindingError` here - the error
    surface is bind-time, not resolve-time, so a misconfiguration
    fails fast.

    For class factories the resolution targets ``cls.__init__``
    (which is where the constructor parameters live), while
    function factories are inspected directly.
    """
    sig = inspect.signature(factory)
    target = factory.__init__ if inspect.isclass(factory) else factory
    hints = inspect.get_annotations(target, eval_str=True)
    params: list[inspect.Parameter] = []
    for raw_param in sig.parameters.values():
        param = (
            raw_param.replace(annotation=hints[raw_param.name])
            if raw_param.name in hints
            else raw_param
        )
        if param.annotation is inspect.Parameter.empty:
            if param.default is inspect.Parameter.empty:
                raise BindingError(
                    f"Cannot auto-inject {factory!r}: parameter "
                    f"{param.name!r} has no annotation and no default."
                )
            # Unannotated-with-default: not injectable, let the
            # factory's own default fill the slot. Skip from the
            # returned list so the wrap below has nothing to do
            # for it.
            continue
        params.append(param)
    return params


def _resolve_auto_inject(
    factory: Callable[..., Any] | Callable[..., Awaitable[Any]],
    explicit: bool,
) -> bool:
    """Effective ``auto_inject`` = explicit-keyword OR ``@inject`` marker."""
    return explicit or bool(getattr(factory, INJECT_ATTR, False))


def _wrap_factory_for_injection(
    factory: Callable[..., Any] | Callable[..., Awaitable[Any]],
    container: "Container",
) -> Callable[..., Any] | Callable[..., Awaitable[Any]]:
    """Return a no-arg factory that resolves annotated params from ``container``.

    Sync factories produce a sync wrapper; async factories
    produce an async wrapper. Signature validation runs once,
    at wrap time, so a misconfigured factory fails at bind-time
    rather than at the first ``resolve`` call. Parameters
    without an annotation are kept on their default (the
    validator has already asserted that any annotation-less
    param carries a default); parameters whose annotation is
    not registered in the container also fall back to the
    default when one exists, otherwise re-raise
    :class:`tripack_contracts.ResolutionError`.
    """
    params = _validate_injectable_signature(factory)

    if inspect.iscoroutinefunction(factory):
        async_fn = cast("Callable[..., Awaitable[Any]]", factory)

        async def wrapped_async() -> Any:
            kwargs: dict[str, Any] = {}
            for param in params:
                try:
                    kwargs[param.name] = await container.aresolve(param.annotation)
                except ResolutionError:
                    if param.default is not inspect.Parameter.empty:
                        continue
                    raise
            return await async_fn(**kwargs)

        return wrapped_async

    sync_fn = cast("Callable[..., Any]", factory)

    def wrapped_sync() -> Any:
        kwargs: dict[str, Any] = {}
        for param in params:
            try:
                kwargs[param.name] = container.resolve(param.annotation)
            except ResolutionError:
                if param.default is not inspect.Parameter.empty:
                    continue
                raise
        return sync_fn(**kwargs)

    return wrapped_sync


def _resolve_lifecycle(
    factory: Callable[..., Any] | Callable[..., Awaitable[Any]],
    explicit: Lifecycle | None,
) -> Lifecycle:
    """Pick the binding's effective lifecycle.

    ``explicit`` (from the ``lifecycle=`` keyword) always wins
    when it is not ``None``. Otherwise the factory is inspected
    for a ``__tripack_lifecycle__`` marker (set by the provider
    helpers in :mod:`tripack_container.providers`); falling back
    to ``Lifecycle.TRANSIENT`` when no marker is present.
    """
    if explicit is not None:
        return explicit
    tagged = getattr(factory, LIFECYCLE_ATTR, None)
    if isinstance(tagged, Lifecycle):
        return tagged
    return Lifecycle.TRANSIENT


def _make_binding(
    token: type[Any],
    factory: Callable[..., Any] | Callable[..., Awaitable[Any]],
    *,
    lifecycle: Lifecycle,
    auto_inject: bool,
) -> Binding:
    """Construct the right :class:`Binding` for a sync-or-async factory.

    Auto-detects async via :func:`inspect.iscoroutinefunction`
    and fills either the ``factory`` or ``async_factory`` slot
    on the resulting binding. Used by both
    :meth:`Container.bind` and :meth:`ContainerBuilder.bind`,
    so the two surfaces register structurally identical
    bindings.
    """
    if inspect.iscoroutinefunction(factory):
        return Binding(
            token=token,
            async_factory=cast("Callable[..., Awaitable[Any]]", factory),
            lifecycle=lifecycle,
            auto_inject=auto_inject,
        )
    return Binding(
        token=token,
        factory=cast("Callable[..., Any]", factory),
        lifecycle=lifecycle,
        auto_inject=auto_inject,
    )


class Container:
    """High-level IoC container backed by a :class:`Resolver`.

    Wraps a private :class:`DependencyGraph` and the matching
    :class:`Resolver`. A Container can be created in two ways:

    - directly via ``Container()`` - empty and **unfrozen**, so
      :meth:`bind` is allowed; useful for ad-hoc wiring;
    - via :meth:`ContainerBuilder.build` - populated with
      pre-registered bindings and **frozen**, so :meth:`bind`
      raises :class:`tripack_contracts.BindingError`.

    The frozen flag is internal: only the builder reaches it
    (through :meth:`_seal`); consumer code does not control it
    directly.
    """

    __slots__ = ("_frozen", "_graph", "_resolver")

    def __init__(self, *, graph: DependencyGraph | None = None) -> None:
        """Create a container, optionally over an existing graph.

        ``graph`` is keyword-only and intended for
        :meth:`ContainerBuilder.build` to hand over a populated,
        soon-to-be-sealed graph. Direct callers normally omit it
        and let the constructor build an empty
        :class:`DependencyGraph`.
        """
        self._graph = graph if graph is not None else DependencyGraph()
        self._resolver = Resolver(self._graph)
        self._frozen = False

    def _seal(self) -> None:
        """Mark this container as sealed; no further :meth:`bind` allowed.

        Internal API, called by :meth:`ContainerBuilder.build`.
        Idempotent: a second call is a no-op.
        """
        self._frozen = True

    # Async overload first: ``Callable[..., T]`` would otherwise mask
    # ``Callable[..., Awaitable[T]]`` since the broader return type
    # matches any return shape (mypy overload-cannot-match).
    @overload
    def bind[T](
        self,
        token: type[T],
        factory: Callable[..., Awaitable[T]],
        *,
        lifecycle: Lifecycle | None = ...,
        auto_inject: bool = ...,
    ) -> None: ...

    @overload
    def bind[T](
        self,
        token: type[T],
        factory: Callable[..., T],
        *,
        lifecycle: Lifecycle | None = ...,
        auto_inject: bool = ...,
    ) -> None: ...

    def bind[T](
        self,
        token: type[T],
        factory: Callable[..., T] | Callable[..., Awaitable[T]],
        *,
        lifecycle: Lifecycle | None = None,
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

        Raises:
            BindingError: when the container has been sealed by
                :meth:`ContainerBuilder.build` (no further binds
                allowed once a container has been built).
        """
        if self._frozen:
            raise BindingError(
                "Container is sealed; bindings can no longer be added "
                "after ContainerBuilder.build(). Re-build from a new "
                "builder to extend the wiring."
            )
        effective_auto_inject = _resolve_auto_inject(factory, auto_inject)
        effective_factory: Callable[..., Any] | Callable[..., Awaitable[Any]] = factory
        if effective_auto_inject:
            effective_factory = _wrap_factory_for_injection(factory, self)
        binding = _make_binding(
            token,
            effective_factory,
            lifecycle=_resolve_lifecycle(factory, lifecycle),
            auto_inject=effective_auto_inject,
        )
        self._graph.register(binding)

    def bind_class[T](
        self, cls: type[T], *, lifecycle: Lifecycle | None = None
    ) -> None:
        """Register ``cls`` as its own factory with automatic injection.

        Equivalent to ``self.bind(cls, cls, lifecycle=lifecycle,
        auto_inject=True)``: the container resolves the ``__init__``
        parameters from its own bindings each time ``cls`` is
        resolved. Parameters with defaults that are not bound in
        the container keep their default value.
        """
        self.bind(cls, cls, lifecycle=lifecycle, auto_inject=True)

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

    @contextmanager
    def scope(self) -> Iterator[Scope]:
        """Open a sync lifetime :class:`Scope` for ``SCOPED`` bindings.

        Convenience wrapper around
        :func:`tripack_runtime.lifetime_scope`: inside the
        ``with`` block, ``SCOPED`` bindings cache on the active
        :class:`Scope`; on exit the scope auto-closes its sync
        teardown targets in LIFO order. The same caveats apply -
        async-only teardown targets are skipped on the sync path,
        use :meth:`ascope` for them.

        .. code-block:: python

            with container.scope() as scope:
                handler = container.resolve(RequestHandler)
                ...
        """
        with lifetime_scope() as s:
            yield s

    @asynccontextmanager
    async def ascope(self) -> AsyncIterator[Scope]:
        """Open an async lifetime :class:`Scope` for ``SCOPED`` bindings.

        Convenience wrapper around
        :func:`tripack_runtime.alifetime_scope`: handles both
        sync and async teardown targets on exit, awaiting
        ``aclose`` where present. Each :class:`asyncio.Task`
        opened inside the surrounding context inherits its own
        copy of the underlying ContextVar, so concurrent
        :func:`asyncio.gather` calls each open and close
        independent scopes.

        .. code-block:: python

            async with container.ascope() as scope:
                handler = await container.aresolve(RequestHandler)
                ...
        """
        async with alifetime_scope() as s:
            yield s
