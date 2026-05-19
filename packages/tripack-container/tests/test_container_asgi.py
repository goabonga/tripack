# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Tests for ``tripack_container.asgi`` against a pure Starlette app.

The point of these tests is to demonstrate that the ASGI layer
ships **without** any FastAPI dependency: a vanilla Starlette
``Starlette()`` application can compose
:func:`container_lifespan` and
:class:`ContainerScopeMiddleware` to get the same lifecycle +
per-request scope as a per-framework adapter would, without
paying any FastAPI coupling.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, Protocol, cast

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from tripack_container import ContainerBuilder
from tripack_container.asgi import ContainerScopeMiddleware, container_lifespan
from tripack_contracts import Lifecycle

if TYPE_CHECKING:
    from tripack_container import Container


class Clock(Protocol):
    """Interface used as a binding token."""

    def now(self) -> int: ...


class SystemClock:
    """One impl."""

    def now(self) -> int:
        return 42


class RequestCounter:
    """SCOPED token to verify per-request caching."""

    def __init__(self) -> None:
        self.value = 0


def _build_container() -> Container:
    builder = ContainerBuilder()
    builder.bind(
        cast("type[Any]", Clock),
        lambda: SystemClock(),
        lifecycle=Lifecycle.SINGLETON,
    )
    builder.bind(RequestCounter, lambda: RequestCounter(), lifecycle=Lifecycle.SCOPED)
    return builder.build()


def _build_starlette_app() -> Starlette:
    """Wire a Starlette app on top of the framework-agnostic ASGI primitives.

    The wiring shape is the analogue of a per-framework adapter
    for a Starlette user:

    - ``lifespan`` consumes :func:`container_lifespan` so the
      container is built at startup and ``aclose``d at
      shutdown;
    - ``middleware`` declares
      :class:`ContainerScopeMiddleware` so every request runs
      inside ``container.ascope()``;
    - handlers resolve from ``request.app.state.container``
      directly (Starlette has no ``Depends`` mechanism).
    """

    @asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[None]:
        async with container_lifespan(app, container_factory=_build_container):
            yield

    async def now(request: Request) -> JSONResponse:
        container = request.app.state.container
        clock = await container.aresolve(cast("type[Any]", Clock))
        return JSONResponse({"now": clock.now()})

    async def incr(request: Request) -> JSONResponse:
        container = request.app.state.container
        counter = await container.aresolve(RequestCounter)
        counter.value += 1
        return JSONResponse({"value": counter.value})

    routes: list[Route] = [
        Route("/now", now),
        Route("/incr", incr),
    ]
    middleware: list[Middleware] = [Middleware(ContainerScopeMiddleware)]
    return Starlette(lifespan=lifespan, routes=routes, middleware=middleware)


def test_starlette_app_resolves_singleton_via_asgi_layer() -> None:
    """The ASGI primitives + a Starlette app expose the container per request.

    ``container_lifespan`` builds the container and stores it on
    ``app.state``; ``ContainerScopeMiddleware`` opens
    ``ascope()`` per request; the handler resolves
    synchronously from the container. No FastAPI involved.
    """
    app = _build_starlette_app()
    with TestClient(app) as client:
        response = client.get("/now")
    assert response.status_code == 200
    assert response.json() == {"now": 42}


def test_starlette_app_scoped_binding_is_per_request() -> None:
    """Each request gets a fresh SCOPED instance with the ASGI middleware."""
    app = _build_starlette_app()
    with TestClient(app) as client:
        first = client.get("/incr").json()
        second = client.get("/incr").json()
    assert first == {"value": 1}
    assert second == {"value": 1}


def test_container_lifespan_aclose_runs_on_shutdown() -> None:
    """``container_lifespan`` calls ``container.aclose`` on context exit."""
    closed = {"flag": False}

    class TornDown:
        def close(self) -> None:
            closed["flag"] = True

    def build() -> Container:
        builder = ContainerBuilder()
        builder.bind(TornDown, TornDown, lifecycle=Lifecycle.SINGLETON)
        return builder.build()

    @asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[None]:
        async with container_lifespan(app, container_factory=build):
            yield

    async def ping(request: Request) -> JSONResponse:
        # Resolve the SINGLETON so it lands in the teardown registry
        # before lifespan shutdown runs.
        await request.app.state.container.aresolve(TornDown)
        return JSONResponse({"ok": True})

    app = Starlette(lifespan=lifespan, routes=[Route("/ping", ping)])
    with TestClient(app) as client:
        client.get("/ping")
    # TestClient exits → lifespan shutdown → container.aclose()
    # → TornDown.close().
    assert closed["flag"] is True


def test_container_scope_middleware_passes_lifespan_through() -> None:
    """Lifespan scopes bypass ``ascope()`` so the outer lifespan owns them.

    A lifespan scope reaching the middleware must be forwarded
    untouched: the per-request scope only applies to ``http``
    and ``websocket`` traffic; lifecycle messages travel
    end-to-end so :func:`container_lifespan` (sitting OUTSIDE
    this middleware in the framework's app) can react to
    startup / shutdown.
    """
    import asyncio
    from collections.abc import MutableMapping
    from typing import Any as _Any

    received: list[str] = []

    async def inner_app(
        scope: MutableMapping[str, _Any],
        receive: Callable[[], Any],
        send: Callable[[MutableMapping[str, _Any]], Any],
    ) -> None:
        received.append(scope["type"])
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                await send({"type": "lifespan.shutdown.complete"})
                return

    container = _build_container()

    wrapped = ContainerScopeMiddleware(inner_app, accessor=lambda _scope: container)

    async def drive() -> None:
        messages: list[MutableMapping[str, _Any]] = [
            {"type": "lifespan.startup"},
            {"type": "lifespan.shutdown"},
        ]
        sent: list[MutableMapping[str, _Any]] = []

        async def receive() -> MutableMapping[str, _Any]:
            return messages.pop(0)

        async def send(message: MutableMapping[str, _Any]) -> None:
            sent.append(message)

        await wrapped({"type": "lifespan"}, receive, send)
        assert received == ["lifespan"]
        assert [m["type"] for m in sent] == [
            "lifespan.startup.complete",
            "lifespan.shutdown.complete",
        ]

    asyncio.run(drive())


def test_default_accessor_reads_from_app_state() -> None:
    """The default accessor reaches ``scope['app'].state.container``."""
    from types import SimpleNamespace

    from tripack_container.asgi import _default_accessor

    container = _build_container()
    app_obj = SimpleNamespace(state=SimpleNamespace(container=container))
    scope: dict[str, Any] = {"app": app_obj}
    assert _default_accessor(scope) is container
