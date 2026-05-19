# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Tests for ``tripack_container.asgi`` against a pure Starlette app.

The point of these tests is to demonstrate that the ASGI layer
ships **without** any FastAPI dependency: a vanilla Starlette
``Starlette()`` application can compose
:func:`container_lifespan` and
:class:`ContainerScopeMiddleware` to get the same lifecycle +
per-request scope as :class:`TripackAPI`, without paying the
FastAPI coupling. The only thing missing in Starlette is the
``Annotated[T, Inject]`` rewriting - Starlette handlers
resolve from the container manually inside the handler body.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Annotated, Any, Protocol, cast

import pytest
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from tripack_container import ContainerBuilder, Inject, InjectionError
from tripack_container.asgi import (
    ContainerScopeMiddleware,
    TripackMiddleware,
    container_lifespan,
    tripack_lifespan,
)
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


class _Notifier(Protocol):
    """Module-level Protocol so annotation eval can resolve it.

    ``parse_inject_params`` calls ``inspect.get_annotations(fn,
    eval_str=True)`` which evaluates string annotations in
    ``fn.__globals__`` - protocols / token types defined inside
    a test function would not resolve. Real-world usage already
    follows the module-level convention, so this is not a real
    limitation, only one the tests have to respect.
    """

    def notify(self, msg: str) -> None: ...


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

    The wiring shape is the analogue of :class:`TripackAPI`
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
    """The ASGI primitives + a Starlette app give the same UX as TripackAPI.

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


def test_tripack_middleware_resolves_dispatch_kwargs_from_container() -> None:
    """A ``TripackMiddleware`` injects ``Annotated[T, Inject]`` into ``dispatch``."""
    captured: dict[str, Any] = {}

    class CaptureMiddleware(TripackMiddleware):
        async def dispatch(
            self,
            scope: Any,
            receive: Any,
            send: Any,
            *,
            clock: Annotated[Clock, Inject],
        ) -> None:
            captured["clock"] = clock
            await self.app(scope, receive, send)

    async def now(request: Request) -> JSONResponse:
        return JSONResponse({"hit": True})

    @asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[None]:
        async with container_lifespan(app, container_factory=_build_container):
            yield

    app = Starlette(
        lifespan=lifespan,
        routes=[Route("/now", now)],
        middleware=[
            Middleware(ContainerScopeMiddleware),
            Middleware(CaptureMiddleware),
        ],
    )
    with TestClient(app) as client:
        assert client.get("/now").json() == {"hit": True}
    assert captured["clock"].now() == 42


def test_tripack_middleware_passes_through_lifespan_scopes() -> None:
    """Lifespan scopes never trigger dispatch on a ``TripackMiddleware``."""
    counter = {"dispatch_calls": 0}

    class TouchyMiddleware(TripackMiddleware):
        async def dispatch(
            self, scope: Any, receive: Any, send: Any, **kwargs: Any
        ) -> None:
            counter["dispatch_calls"] += 1
            await self.app(scope, receive, send)

    async def ping(request: Request) -> JSONResponse:
        return JSONResponse({"ok": True})

    @asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[None]:
        async with container_lifespan(app, container_factory=_build_container):
            yield

    app = Starlette(
        lifespan=lifespan,
        routes=[Route("/ping", ping)],
        middleware=[
            Middleware(ContainerScopeMiddleware),
            Middleware(TouchyMiddleware),
        ],
    )
    with TestClient(app) as client:
        client.get("/ping")
        client.get("/ping")
    # Lifespan startup + shutdown do NOT trigger dispatch;
    # only the two HTTP requests do.
    assert counter["dispatch_calls"] == 2


def test_tripack_lifespan_injects_keyword_only_params() -> None:
    """Decorator factory resolves ``Annotated[T, Inject]`` kwargs at startup."""
    captured: dict[str, Any] = {}

    @tripack_lifespan(container_factory=_build_container)
    @asynccontextmanager
    async def lifespan(
        app: Starlette,
        *,
        clock: Annotated[Clock, Inject],
    ) -> AsyncIterator[None]:
        captured["startup_clock"] = clock.now()
        yield
        captured["shutdown"] = True

    async def hello(request: Request) -> JSONResponse:
        return JSONResponse({"hi": True})

    app = Starlette(lifespan=lifespan, routes=[Route("/hi", hello)])
    with TestClient(app) as client:
        client.get("/hi")
    assert captured["startup_clock"] == 42
    assert captured["shutdown"] is True


def test_tripack_lifespan_optional_returns_none_when_unbound() -> None:
    """``Annotated[T | None, Inject]`` resolves to ``None`` on a missing binding."""
    captured: dict[str, Any] = {}

    @tripack_lifespan(container_factory=_build_container)
    @asynccontextmanager
    async def lifespan(
        app: Starlette,
        *,
        notifier: Annotated[_Notifier | None, Inject],
    ) -> AsyncIterator[None]:
        captured["notifier"] = notifier
        yield

    async def hello(request: Request) -> JSONResponse:
        return JSONResponse({"hi": True})

    app = Starlette(lifespan=lifespan, routes=[Route("/hi", hello)])
    with TestClient(app) as client:
        client.get("/hi")
    assert captured["notifier"] is None


def test_tripack_middleware_raises_injection_error_without_container() -> None:
    """Default accessor failure surfaces as ``InjectionError``.

    Without the right ``scope['app'].state.container`` shape the
    accessor raises ``KeyError`` / ``AttributeError``;
    :class:`TripackMiddleware` converts those to a wrapping
    :class:`InjectionError` with a wiring hint.
    """
    import asyncio

    class _M(TripackMiddleware):
        async def dispatch(
            self,
            scope: Any,
            receive: Any,
            send: Any,
            *,
            clock: Annotated[Clock, Inject],
        ) -> None:
            await self.app(scope, receive, send)

    async def inner(scope: Any, receive: Any, send: Any) -> None: ...

    mw = _M(inner)

    async def drive() -> None:
        async def receive() -> Any:
            raise AssertionError("not called")

        async def send(_: Any) -> None: ...

        with pytest.raises(InjectionError):
            # ``scope['app'].state.container`` does not exist; the
            # accessor raises ``AttributeError`` which the middleware
            # converts to ``InjectionError``.
            await mw({"type": "http", "app": object()}, receive, send)

    asyncio.run(drive())


def test_tripack_middleware_without_dispatch_raises_type_error() -> None:
    """Subclassing without defining ``dispatch`` is caught at class creation.

    ``__init_subclass__`` raises :class:`TypeError` rather than
    letting the missing method surface later at first request,
    so the misuse is visible at import time.
    """
    with pytest.raises(TypeError, match="must define a ``dispatch`` method"):
        # ``class`` statement inside ``pytest.raises`` triggers
        # ``__init_subclass__`` which raises. Control never
        # reaches code after the class body in the success case.
        class _NoDispatch(TripackMiddleware):
            pass


def test_default_accessor_reads_from_app_state() -> None:
    """The default accessor reaches ``scope['app'].state.container``."""
    from types import SimpleNamespace

    from tripack_container.asgi import _default_accessor

    container = _build_container()
    app_obj = SimpleNamespace(state=SimpleNamespace(container=container))
    scope: dict[str, Any] = {"app": app_obj}
    assert _default_accessor(scope) is container
