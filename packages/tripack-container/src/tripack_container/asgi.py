# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""ASGI-agnostic primitives for the Tripack container.

Two building blocks composable into any ASGI framework:

- :func:`container_lifespan` - an ``@asynccontextmanager``
  that builds the container at startup and ``aclose``s it at
  shutdown. Compatible with any framework that accepts a
  lifespan context manager (Starlette, FastAPI, Litestar,
  pure-ASGI lifespan handlers).
- :class:`ContainerScopeMiddleware` - a pure ASGI middleware
  that opens :meth:`Container.ascope` around every HTTP /
  WebSocket request. Compatible with any ASGI app.

These primitives carry **no FastAPI dependency**. The
framework-specific adapters layer on top:

- :mod:`tripack_container.fastapi` adds ``TripackAPI`` which
  composes these primitives plus an inject-aware
  :class:`fastapi.routing.APIRoute` for ``Annotated[T, Inject]``
  parameter resolution at route registration time.
- A future :mod:`tripack_container.starlette` module would do
  the same on top of Starlette's route classes; a pure-ASGI
  user can also use the primitives directly without any
  framework adapter (they just resolve from the container
  manually inside handlers).
"""

from __future__ import annotations

import inspect
from collections.abc import AsyncIterator, Awaitable, Callable, MutableMapping
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from functools import wraps
from typing import TYPE_CHECKING, Any

from tripack_container._inject import (
    InjectionError,
    parse_inject_params,
    resolve_inject_kwargs,
)

if TYPE_CHECKING:
    from tripack_container.container import Container


ContainerFactory = Callable[[], "Container | Awaitable[Container]"]
"""Public name for the factory shape accepted by both helpers."""

ASGIScope = MutableMapping[str, Any]
"""ASGI scope mapping passed to every ``__call__``."""

ASGIReceive = Callable[[], Awaitable[MutableMapping[str, Any]]]
"""Coroutine that pulls the next message from the ASGI stream."""

ASGISend = Callable[[MutableMapping[str, Any]], Awaitable[None]]
"""Coroutine that pushes a message onto the ASGI stream."""

ASGIApp = Callable[[ASGIScope, ASGIReceive, ASGISend], Awaitable[None]]
"""Pure ASGI application callable shape."""

ContainerAccessor = Callable[[ASGIScope], "Container"]
"""Strategy for locating the container given an ASGI scope."""


@asynccontextmanager
async def container_lifespan(
    app: Any,
    *,
    container_factory: ContainerFactory,
) -> AsyncIterator[None]:
    """Build the container for the duration of ``app``'s lifespan.

    Usage as a lifespan in any framework that takes an async
    context manager:

    ```python
    @asynccontextmanager
    async def lifespan(app):
        async with container_lifespan(app, container_factory=build):
            yield  # user-supplied startup logic can read app.state.container here
    ```

    The factory may be sync or async; the helper awaits it when
    it returns an awaitable. The container instance is stored
    on ``app.state.container`` when the framework's app object
    exposes a ``state`` attribute (the Starlette/FastAPI
    convention) so :class:`ContainerScopeMiddleware`'s default
    accessor can find it without extra configuration.

    On exit (normal or exceptional) :meth:`Container.aclose`
    runs so SINGLETON teardown targets release in LIFO order.
    """
    produced = container_factory()
    container = await produced if inspect.isawaitable(produced) else produced
    if hasattr(app, "state"):
        app.state.container = container
    try:
        yield
    finally:
        await container.aclose()


class ContainerScopeMiddleware:
    """ASGI middleware opening a per-request ``Container`` scope.

    Wraps any ASGI app; for every ``http`` and ``websocket``
    request runs the inner app inside ``container.ascope()`` so
    SCOPED bindings cache per request. ``lifespan`` messages
    pass through untouched - lifecycle management belongs to
    :func:`container_lifespan` or the host framework, not to
    this middleware.

    The container is read from
    ``scope['app'].state.container`` by default, which matches
    what :func:`container_lifespan` writes. Pass a custom
    ``accessor`` to integrate with a framework that keeps the
    container elsewhere (e.g. read it from
    ``scope['extensions']`` or a contextvar).
    """

    __slots__ = ("accessor", "app")

    def __init__(
        self,
        app: ASGIApp,
        *,
        accessor: ContainerAccessor | None = None,
    ) -> None:
        """Wrap ``app`` and remember how to locate the container.

        ``accessor`` receives the ASGI ``scope`` mapping and
        must return a :class:`Container`. Defaults to
        ``scope['app'].state.container``.
        """
        self.app = app
        self.accessor = accessor or _default_accessor

    async def __call__(
        self, scope: ASGIScope, receive: ASGIReceive, send: ASGISend
    ) -> None:
        """Open ``ascope()`` around the inner app for HTTP / WS scopes."""
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        container = self.accessor(scope)
        async with container.ascope():
            await self.app(scope, receive, send)


def _default_accessor(scope: ASGIScope) -> Container:
    """Read the container from ``scope['app'].state.container``."""
    container: Container = scope["app"].state.container
    return container


class TripackMiddleware:
    """ASGI middleware base class that resolves ``Annotated[T, Inject]``.

    Subclasses define a ``dispatch`` method with whatever
    ``Annotated[T, Inject]`` keyword-only parameters they need;
    the base class scans the signature once at class creation
    (``__init_subclass__``) and resolves the marked parameters
    from the container on every call before invoking
    ``dispatch``. The pattern mirrors Starlette's
    :class:`starlette.middleware.base.BaseHTTPMiddleware`
    (override ``dispatch``, not ``__call__``).

    ```python
    class LoggingMiddleware(TripackMiddleware):
        async def dispatch(
            self,
            scope, receive, send,
            *,
            log: Annotated[Logger, Inject],
        ):
            log.info("request: %s", scope.get("path"))
            await self.app(scope, receive, send)
    ```

    The ``dispatch`` method is **not** declared on the base
    class: declaring it there would force every subclass into a
    common signature, which conflicts with the typed
    ``Annotated[T, Inject]`` keyword parameters subclasses
    legitimately want to use. ``__init_subclass__`` enforces
    the presence of ``dispatch`` at class creation
    (``TypeError`` if missing) so the duck-typed call from
    :meth:`__call__` is safe at runtime.

    Per-call resolution means SCOPED tokens work **when** the
    middleware sits inner to a :class:`ContainerScopeMiddleware`
    (i.e. the scope is already open). :class:`TripackAPI`
    handles the ordering automatically; in plain Starlette the
    user controls the ordering via the ``middleware=[...]``
    list (put :class:`ContainerScopeMiddleware` first / outer).
    SCOPED requested without an active scope raises
    :class:`tripack_contracts.ScopeError` per the normal
    Tripack semantics.

    The container is read from
    ``scope['app'].state.container`` by default. Pass a custom
    ``accessor`` to :meth:`__init__` to integrate with a
    framework that keeps it elsewhere.
    """

    _inject_params: dict[str, tuple[object, bool]]

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Parse ``dispatch`` once at subclass creation.

        The introspection happens at class definition, not at
        instance creation, so repeated middleware
        instantiations do not re-walk the signature. Each
        subclass gets its own ``_inject_params`` map.

        Subclasses must define a ``dispatch`` method; the
        lookup is duck-typed at runtime to avoid an LSP signature
        clash with the user's typed ``Annotated[T, Inject]``
        keyword parameters. ``AttributeError`` here means the
        subclass forgot to define one.
        """
        super().__init_subclass__(**kwargs)
        dispatch = getattr(cls, "dispatch", None)
        if dispatch is None:
            raise TypeError(
                f"{cls.__name__} must define a ``dispatch`` method - "
                "see ``TripackMiddleware`` docstring for the pattern."
            )
        cls._inject_params = parse_inject_params(dispatch)

    def __init__(
        self,
        app: ASGIApp,
        *,
        accessor: ContainerAccessor | None = None,
    ) -> None:
        """Store the wrapped app + the optional accessor override."""
        self.app = app
        self._accessor: ContainerAccessor = accessor or _default_accessor

    async def __call__(
        self, scope: ASGIScope, receive: ASGIReceive, send: ASGISend
    ) -> None:
        """ASGI entry: resolve injects, forward to ``dispatch``.

        Non-HTTP / non-WebSocket scopes (``lifespan``) bypass
        the resolution and the dispatch entirely - middleware
        only intercept request scopes.
        """
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        try:
            container = self._accessor(scope)
        except (AttributeError, KeyError) as exc:
            raise InjectionError(
                f"Cannot locate the container from scope; the default "
                f"accessor expects ``scope['app'].state.container``. "
                f"Original lookup failure: {exc!r}"
            ) from exc
        kwargs = await resolve_inject_kwargs(self._inject_params, container)
        # Route through ``_invoke_dispatch`` so mypy's strict LSP
        # variance check does not see ``self.dispatch`` directly:
        # subclasses declare a typed ``Annotated[T, Inject]``
        # signature that would otherwise be flagged as
        # incompatible with any base-class declaration.
        # ``__init_subclass__`` guarantees the attribute exists
        # at runtime.
        await _invoke_dispatch(self, scope, receive, send, kwargs)


async def _invoke_dispatch(
    instance: Any,
    scope: ASGIScope,
    receive: ASGIReceive,
    send: ASGISend,
    kwargs: dict[str, Any],
) -> None:
    """Indirect ``await instance.dispatch(...)`` through ``Any``.

    The helper exists purely to bypass mypy's strict
    ``[override]`` variance check on subclasses of
    :class:`TripackMiddleware`. By typing ``instance`` as
    ``Any`` here, the call site does not constrain
    ``dispatch``'s signature - subclasses are free to declare
    ``Annotated[T, Inject]`` keyword-only parameters.
    """
    await instance.dispatch(scope, receive, send, **kwargs)


def tripack_lifespan(
    *, container_factory: ContainerFactory
) -> Callable[
    [Callable[..., AbstractAsyncContextManager[None]]],
    Callable[[Any], AbstractAsyncContextManager[None]],
]:
    """Decorator factory: turn an inject-aware lifespan into a plain one.

    Wraps a user-defined ``@asynccontextmanager`` lifespan that
    declares ``Annotated[T, Inject]`` keyword parameters,
    yielding back a one-arg lifespan compatible with any
    Starlette / FastAPI / Litestar / pure-ASGI lifespan
    keyword. The wrapper:

    1. Composes :func:`container_lifespan` around the user
       function so the container is built before the user
       body runs and ``aclose``d after it exits.
    2. Introspects the user lifespan's signature once and, at
       startup, resolves each ``Inject`` parameter from the
       freshly built container.
    3. Invokes ``user_lifespan(app, **resolved)`` and yields.

    Use as the canonical lifespan helper for non-TripackAPI
    frameworks; :class:`TripackAPI` handles the same
    introspection internally so you do not need this decorator
    when using it.

    Example (Starlette):

    ```python
    @tripack_lifespan(container_factory=build_container)
    @asynccontextmanager
    async def lifespan(app, *, cache: Annotated[Cache, Inject]):
        await cache.warmup()
        yield

    app = Starlette(lifespan=lifespan, ...)
    ```

    Inject parameters that resolve to a SCOPED binding raise
    :class:`tripack_contracts.ScopeError` because no scope is
    active at startup - SCOPED is intentionally per-request.
    Use SINGLETON / TRANSIENT instead.
    """

    def _wrap(
        user_lifespan: Callable[..., AbstractAsyncContextManager[None]],
    ) -> Callable[[Any], AbstractAsyncContextManager[None]]:
        inject_params = parse_inject_params(user_lifespan)

        @wraps(user_lifespan)
        @asynccontextmanager
        async def _wrapped(app: Any) -> AsyncIterator[None]:
            async with container_lifespan(app, container_factory=container_factory):
                container = getattr(app, "state", None)
                container = getattr(container, "container", None)
                kwargs = await resolve_inject_kwargs(inject_params, container)
                async with user_lifespan(app, **kwargs):
                    yield

        return _wrapped

    return _wrap
