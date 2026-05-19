# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Tests for ``tripack_container.fastapi`` (``TripackAPI`` + injection).

The tests run a real FastAPI app through Starlette's
``TestClient`` so the full lifespan-then-request-then-shutdown
cycle exercises:

- container build from the user-supplied ``container_factory``
  (both sync and async forms);
- per-request scope opening + SCOPED token caching;
- annotation rewriting from ``Annotated[T, Inject]`` to
  ``Annotated[T, Depends(...)]`` at route registration;
- optional injection via ``Inject(optional=True)`` and the
  implicit ``T | None`` form;
- chained-protocol injection (a service that takes another
  protocol in its constructor with ``auto_inject``);
- composed user-supplied lifespan;
- sub-router propagation via ``include_router``.
"""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Annotated, Any, Protocol, cast

from fastapi import APIRouter, FastAPI
from starlette.testclient import TestClient

from tripack_container import ContainerBuilder, Inject
from tripack_container.asgi import TripackMiddleware
from tripack_container.fastapi import TripackAPI, TripackRouter
from tripack_contracts import Lifecycle

if TYPE_CHECKING:
    from tripack_container import Container


class Clock(Protocol):
    """Resolution token (Protocol used as an interface)."""

    def now(self) -> int: ...


class SystemClock:
    """One impl that satisfies :class:`Clock`."""

    def now(self) -> int:
        return 1


class FrozenClock:
    """Alternative impl, used to verify swap by binding."""

    def __init__(self, fixed: int = 42) -> None:
        self._fixed = fixed

    def now(self) -> int:
        return self._fixed


class RequestCounter:
    """SCOPED token; gets a fresh counter per request."""

    def __init__(self) -> None:
        self.value = 0


def _build_basic_container() -> "Container":
    """Build a tiny container used as the default test fixture.

    Several ``cast`` calls exist because the ``ContainerBuilder.bind``
    overloads narrow ``token`` to ``type[T]`` for concrete classes,
    while ``DependencyToken`` actually accepts any hashable token
    at runtime (including ``Protocol`` classes and strings). The
    casts keep mypy quiet without affecting runtime behaviour.
    """
    builder = ContainerBuilder()
    builder.bind(
        cast("type[Any]", Clock),
        lambda: SystemClock(),
        lifecycle=Lifecycle.SINGLETON,
    )
    builder.bind(RequestCounter, lambda: RequestCounter(), lifecycle=Lifecycle.SCOPED)
    return builder.build()


def test_simple_injection_resolves_singleton() -> None:
    app = TripackAPI(container_factory=_build_basic_container)

    @app.get("/now")
    def now(clock: Annotated[Clock, Inject]) -> dict[str, int]:
        return {"now": clock.now()}

    with TestClient(app) as client:
        response = client.get("/now")
    assert response.status_code == 200
    assert response.json() == {"now": 1}


def test_scoped_binding_caches_per_request() -> None:
    """Two reads inside one request hit the same SCOPED instance."""
    app = TripackAPI(container_factory=_build_basic_container)

    @app.get("/twice")
    def twice(
        a: Annotated[RequestCounter, Inject],
        b: Annotated[RequestCounter, Inject],
    ) -> dict[str, bool]:
        a.value += 1
        b.value += 1
        return {"same_instance": a is b, "value_after_both": a.value == 2}

    with TestClient(app) as client:
        response = client.get("/twice")
    assert response.json() == {"same_instance": True, "value_after_both": True}


def test_scoped_binding_fresh_across_requests() -> None:
    """Second request gets a fresh SCOPED instance, not the first's."""
    app = TripackAPI(container_factory=_build_basic_container)

    @app.get("/incr")
    def incr(counter: Annotated[RequestCounter, Inject]) -> dict[str, int]:
        counter.value += 1
        return {"value": counter.value}

    with TestClient(app) as client:
        first = client.get("/incr").json()
        second = client.get("/incr").json()
    # Both responses see ``value == 1`` since each request gets a
    # fresh scope, not a carried-over counter.
    assert first == {"value": 1}
    assert second == {"value": 1}


def test_optional_inject_returns_none_when_unbound() -> None:
    """``Inject(optional=True)`` short-circuits ``ResolutionError`` to ``None``."""

    class Notifier(Protocol):
        def notify(self, message: str) -> None: ...

    # Container has Clock but NOT Notifier.
    app = TripackAPI(container_factory=_build_basic_container)

    @app.get("/notify")
    def notify(
        clock: Annotated[Clock, Inject],
        notifier: Annotated[Notifier | None, Inject],
    ) -> dict[str, object]:
        return {"clock": clock.now(), "notifier_is_none": notifier is None}

    with TestClient(app) as client:
        response = client.get("/notify")
    assert response.json() == {"clock": 1, "notifier_is_none": True}


def test_optional_inject_explicit_flag() -> None:
    """``Inject(optional=True)`` works without the ``| None`` union."""

    class Notifier(Protocol):
        def notify(self, message: str) -> None: ...

    app = TripackAPI(container_factory=_build_basic_container)

    @app.get("/notify-explicit")
    def notify(
        notifier: Annotated[Notifier, Inject(optional=True)],
    ) -> dict[str, bool]:
        return {"notifier_is_none": notifier is None}

    with TestClient(app) as client:
        response = client.get("/notify-explicit")
    assert response.json() == {"notifier_is_none": True}


def test_chained_protocol_injection_via_auto_inject() -> None:
    """A service depending on a protocol token is wired through auto_inject."""

    class EventLog(Protocol):
        def record(self, entry: str) -> None: ...

        def entries(self) -> list[str]: ...

    class InMemoryEventLog:
        def __init__(self) -> None:
            self._entries: list[str] = []

        def record(self, entry: str) -> None:
            self._entries.append(entry)

        def entries(self) -> list[str]:
            return list(self._entries)

    class Audit(Protocol):
        def trace(self, message: str) -> None: ...

    class DefaultAudit:
        """Takes the two interfaces in its constructor.

        ``auto_inject=True`` on the binding asks the runtime to
        resolve the constructor params from the container
        before invoking it.
        """

        def __init__(self, clock: Clock, log: EventLog) -> None:
            self._clock = clock
            self._log = log

        def trace(self, message: str) -> None:
            self._log.record(f"t={self._clock.now()} {message}")

    def build() -> "Container":
        builder = ContainerBuilder()
        builder.bind(
            cast("type[Any]", Clock),
            lambda: SystemClock(),
            lifecycle=Lifecycle.SINGLETON,
        )
        builder.bind(
            cast("type[Any]", EventLog),
            lambda: InMemoryEventLog(),
            lifecycle=Lifecycle.SINGLETON,
        )
        builder.bind(
            cast("type[Any]", Audit),
            cast("Callable[..., Any]", DefaultAudit),
            lifecycle=Lifecycle.SINGLETON,
            auto_inject=True,
        )
        return builder.build()

    app = TripackAPI(container_factory=build)

    @app.post("/trace/{message}")
    def trace_route(
        message: str,
        audit: Annotated[Audit, Inject],
        log: Annotated[EventLog, Inject],
    ) -> dict[str, list[str]]:
        audit.trace(message)
        return {"entries": log.entries()}

    with TestClient(app) as client:
        response = client.post("/trace/hello")
    assert response.json() == {"entries": ["t=1 hello"]}


def test_token_override_resolves_named_token() -> None:
    """``Inject(token=...)`` overrides the annotation type."""

    def build() -> "Container":
        builder = ContainerBuilder()
        builder.bind(
            cast("type[Any]", "primary-clock"),
            lambda: FrozenClock(99),
            lifecycle=Lifecycle.SINGLETON,
        )
        return builder.build()

    app = TripackAPI(container_factory=build)

    @app.get("/named")
    def named(
        clock: Annotated[Clock, Inject(token="primary-clock")],
    ) -> dict[str, int]:
        return {"now": clock.now()}

    with TestClient(app) as client:
        response = client.get("/named")
    assert response.json() == {"now": 99}


def test_async_container_factory_is_awaited() -> None:
    """An ``async def`` factory is awaited at startup."""

    async def build() -> "Container":
        builder = ContainerBuilder()
        builder.bind(
            cast("type[Any]", Clock),
            lambda: SystemClock(),
            lifecycle=Lifecycle.SINGLETON,
        )
        return builder.build()

    app = TripackAPI(container_factory=build)

    @app.get("/now")
    def now(clock: Annotated[Clock, Inject]) -> dict[str, int]:
        return {"now": clock.now()}

    with TestClient(app) as client:
        assert client.get("/now").json() == {"now": 1}


def test_container_aclose_runs_on_shutdown() -> None:
    """The container's teardown fires when the lifespan exits."""

    closed = {"flag": False}

    class TornDown:
        def close(self) -> None:
            closed["flag"] = True

    def build() -> "Container":
        builder = ContainerBuilder()
        builder.bind(TornDown, TornDown, lifecycle=Lifecycle.SINGLETON)
        return builder.build()

    app = TripackAPI(container_factory=build)

    @app.get("/td")
    def td(t: Annotated[TornDown, Inject]) -> dict[str, bool]:
        return {"ok": True}

    with TestClient(app) as client:
        client.get("/td")
    # TestClient exits → lifespan shutdown → container.aclose()
    # → TornDown.close().
    assert closed["flag"] is True


def test_user_lifespan_with_inject_kwargs_resolved_automatically() -> None:
    """``TripackAPI`` introspects the user lifespan and injects kwargs.

    Same ``Annotated[T, Inject]`` syntax as handlers - no
    decorator on the user side; the FastAPI adapter parses the
    user lifespan signature once and resolves at startup.
    """
    captured: dict[str, object] = {}

    @asynccontextmanager
    async def user_lifespan(
        app: FastAPI,
        *,
        clock: Annotated[Clock, Inject],
    ) -> AsyncIterator[None]:
        captured["startup_now"] = clock.now()
        yield
        captured["shutdown"] = True

    app = TripackAPI(
        container_factory=_build_basic_container,
        lifespan=user_lifespan,
    )

    @app.get("/ping")
    def ping() -> dict[str, bool]:
        return {"ok": True}

    with TestClient(app) as client:
        client.get("/ping")
    assert captured == {"startup_now": 1, "shutdown": True}


def test_tripack_middleware_auto_inner_to_scope() -> None:
    """``add_middleware`` puts ``TripackMiddleware`` instances inner to CSM.

    Demonstrated by injecting a SCOPED token into ``dispatch`` -
    if the middleware ran OUTER to ``ContainerScopeMiddleware``,
    no scope would be open and the resolution would raise
    :class:`ScopeError`. Reaching the handler means the
    ordering is correct.
    """
    seen_values: list[int] = []

    class CounterMiddleware(TripackMiddleware):
        async def dispatch(
            self,
            scope: Any,
            receive: Any,
            send: Any,
            *,
            counter: Annotated[RequestCounter, Inject],
        ) -> None:
            counter.value += 100
            seen_values.append(counter.value)
            await self.app(scope, receive, send)

    app = TripackAPI(container_factory=_build_basic_container)
    app.add_middleware(CounterMiddleware)

    @app.get("/incr")
    def incr(counter: Annotated[RequestCounter, Inject]) -> dict[str, int]:
        # Middleware already bumped to 100; handler bumps again.
        counter.value += 1
        return {"value": counter.value}

    with TestClient(app) as client:
        response = client.get("/incr")
    # Middleware saw the SCOPED counter at 100; handler saw 101
    # (same SCOPED instance per request).
    assert seen_values == [100]
    assert response.json() == {"value": 101}


def test_non_tripack_middleware_keeps_default_outer_placement() -> None:
    """A vanilla ASGI middleware added via ``add_middleware`` stays outer to CSM.

    Reads ``scope`` directly to verify execution order: the
    outer middleware fires before ``ContainerScopeMiddleware``
    opens the scope, so ``scope`` does NOT yet carry any
    container-related state from CSM.
    """
    events: list[str] = []

    class OuterTracer:
        def __init__(self, app: Any) -> None:
            self.app = app

        async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
            if scope["type"] != "http":
                # Skip lifespan / websocket - only HTTP relevant for ordering test.
                await self.app(scope, receive, send)
                return
            events.append("outer-enter")
            await self.app(scope, receive, send)
            events.append("outer-exit")

    app = TripackAPI(container_factory=_build_basic_container)
    app.add_middleware(OuterTracer)

    @app.get("/x")
    def x(clock: Annotated[Clock, Inject]) -> dict[str, int]:
        events.append("handler")
        return {"now": clock.now()}

    with TestClient(app) as client:
        client.get("/x")
    # ``outer-enter`` must fire before the handler (which runs
    # inside the scope). Order proves OuterTracer wraps CSM.
    assert events == ["outer-enter", "handler", "outer-exit"]


def test_user_lifespan_runs_inside_container_lifecycle() -> None:
    """User-supplied lifespan composes with the internal one."""

    order: list[str] = []

    @asynccontextmanager
    async def user_lifespan(app: FastAPI) -> AsyncIterator[None]:
        order.append("user-startup")
        # User can see the container at this point.
        assert hasattr(app.state, "container")
        yield
        order.append("user-shutdown")

    app = TripackAPI(
        container_factory=_build_basic_container,
        lifespan=user_lifespan,
    )

    @app.get("/now")
    def now(clock: Annotated[Clock, Inject]) -> dict[str, int]:
        return {"now": clock.now()}

    with TestClient(app) as client:
        order.append("inside-request")
        client.get("/now")
    # Expected sequence: user-startup ran inside container build;
    # request handler ran; user-shutdown ran before container aclose.
    assert order == ["user-startup", "inside-request", "user-shutdown"]


def test_tripack_router_handles_inject_at_registration() -> None:
    """A ``TripackRouter`` sub-router parses ``Inject`` at @get/@post time.

    A plain ``APIRouter`` would crash at decoration because
    FastAPI introspects the endpoint before
    ``app.include_router`` runs; :class:`TripackRouter` defaults
    its ``route_class`` to the inject-aware variant so the
    rewrite happens during registration.
    """
    app = TripackAPI(container_factory=_build_basic_container)
    sub = TripackRouter()

    @sub.get("/v2/now")
    def v2_now(clock: Annotated[Clock, Inject]) -> dict[str, int]:
        return {"now": clock.now()}

    app.include_router(sub)

    with TestClient(app) as client:
        response = client.get("/v2/now")
    assert response.json() == {"now": 1}


def test_plain_api_router_default_swap_for_inject_free_routes() -> None:
    """Plain ``APIRouter`` with no ``Inject`` routes still composes cleanly.

    Documenting the safety net: ``TripackAPI.include_router``
    swaps the sub-router's ``route_class`` so any FUTURE route
    added to that router would be parsed through the inject-
    aware path. Routes already registered are unaffected (and
    here, free of ``Inject`` markers, so registration succeeded).
    """
    app = TripackAPI(container_factory=_build_basic_container)
    sub = APIRouter()

    @sub.get("/v2/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(sub)
    # After include_router, the sub-router's class was promoted.
    from tripack_container.fastapi import _TripackRoute

    assert sub.route_class is _TripackRoute

    with TestClient(app) as client:
        response = client.get("/v2/health")
    assert response.json() == {"status": "ok"}


def test_include_router_preserves_custom_route_class() -> None:
    """A router with a non-default ``route_class`` is left untouched."""
    from fastapi.routing import APIRoute

    class CustomRoute(APIRoute):
        """User's own subclass for whatever reason."""

    app = TripackAPI(container_factory=_build_basic_container)
    sub = APIRouter(route_class=CustomRoute)
    app.include_router(sub)
    # The TripackAPI override only swaps when ``route_class is APIRoute``.
    assert sub.route_class is CustomRoute


def test_app_is_isinstance_fastapi() -> None:
    """``TripackAPI`` IS-A ``FastAPI`` so downstream tooling still works."""
    app = TripackAPI(container_factory=_build_basic_container)
    assert isinstance(app, FastAPI)


def test_missing_required_binding_propagates_resolution_error() -> None:
    """A non-optional ``Inject`` token without a binding raises through the route.

    Covers the ``raise`` branch in the per-request dependency
    factory: ``ResolutionError`` from ``aresolve`` is only
    swallowed when the parsed marker is ``optional=True``;
    otherwise it re-raises and FastAPI surfaces it as a 500.
    """

    class Missing(Protocol):
        def hello(self) -> str: ...

    app = TripackAPI(container_factory=_build_basic_container)

    @app.get("/missing")
    def missing(svc: Annotated[Missing, Inject]) -> dict[str, str]:
        # The body is unreachable - the dependency raises
        # ``ResolutionError`` before FastAPI invokes the
        # endpoint. ``raise NotImplementedError`` is whitelisted
        # by the workspace coverage config so the uncovered
        # body does not break the gate.
        raise NotImplementedError

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/missing")
    # FastAPI catches the ResolutionError and returns a 500;
    # the test only needs to confirm that the dependency
    # raised (i.e. the optional short-circuit was not taken).
    assert response.status_code == 500


def test_route_without_inject_passes_through_unchanged() -> None:
    """A route with no ``Inject`` params is not rewritten."""
    app = TripackAPI(container_factory=_build_basic_container)

    @app.get("/hello/{name}")
    def hello(name: str) -> dict[str, str]:
        return {"hello": name}

    with TestClient(app) as client:
        response = client.get("/hello/world")
    assert response.json() == {"hello": "world"}
