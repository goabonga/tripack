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
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

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
