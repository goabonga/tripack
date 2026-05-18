# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""FastAPI application: lifespan + per-request scope + Depends adapter.

The integration shape:

- ``lifespan`` builds the :class:`Container` at startup, exposes
  it on ``app.state``, awaits the container's ``aclose`` on
  shutdown so SINGLETON teardown runs once per process lifetime.
- ``request_scope`` middleware opens a per-request
  :class:`Scope` via ``container.ascope()`` so SCOPED bindings
  resolve into a fresh cache for each HTTP request.
- ``from_container(token)`` returns a callable suitable for
  :func:`fastapi.Depends`; the wrapped function pulls the
  requested token out of the container *during* request
  handling, which means it sees the open scope from the
  middleware above.
"""

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Request, Response

from fastapi_basic.services import Clock, EventLog, RequestId
from fastapi_basic.wiring import build_container
from tripack_container import Container


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Build the container at startup, ``aclose`` it on shutdown.

    ``app.state.container`` is the discovery point for every
    downstream adapter; the middleware below reads it through
    the request handle, the ``Depends`` adapter through the
    same path.
    """
    container = build_container()
    app.state.container = container
    try:
        yield
    finally:
        await container.aclose()


def _container_of(request: Request) -> Container:
    """Pull the container off the per-app state."""
    container: Container = request.app.state.container
    return container


def from_container[T](token: type[T]) -> Callable[[Request], T]:
    """Build a FastAPI dependency that resolves ``token`` from the container.

    Used as ``param: T = Depends(from_container(T))``. The
    returned callable is what FastAPI introspects; the inner
    body fires per request and reads the live container.
    """

    def _depend(request: Request) -> T:
        return _container_of(request).resolve(token)

    return _depend


# Module-level ``Annotated`` aliases for the FastAPI 0.95+
# dependency-injection style. The ``Depends(...)`` call is
# evaluated once at import time and stored in
# ``Annotated.__metadata__``; FastAPI introspects the alias
# when a route declares one of these as a parameter
# annotation. The shape avoids ruff B008 (which warns on
# function calls in default values - here there is no
# default, only an annotation).
ClockDep = Annotated[Clock, Depends(from_container(Clock))]
RequestIdDep = Annotated[RequestId, Depends(from_container(RequestId))]
EventLogDep = Annotated[EventLog, Depends(from_container(EventLog))]


def create_app() -> FastAPI:
    """Build the FastAPI app, register middleware and routes."""
    app = FastAPI(lifespan=lifespan)

    @app.middleware("http")
    async def request_scope(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Wrap each request in an ``ascope`` so SCOPED bindings cache per-request."""
        async with _container_of(request).ascope():
            return await call_next(request)

    @app.get("/now")
    def now(clock: ClockDep) -> dict[str, float]:
        """Return the current wall-clock reading from the SINGLETON Clock."""
        return {"now": clock.now()}

    @app.get("/request-id")
    def request_id(rid: RequestIdDep) -> dict[str, str]:
        """Return the SCOPED request id; differs across HTTP requests."""
        return {"request_id": rid.value}

    @app.post("/events")
    def append_event(
        message: str,
        clock: ClockDep,
        rid: RequestIdDep,
        log: EventLogDep,
    ) -> dict[str, Any]:
        """Record an entry tagged with the request's clock + id."""
        log.record(clock.now(), rid.value, message)
        return {"count": len(log.all()), "request_id": rid.value}

    @app.get("/events")
    def list_events(log: EventLogDep) -> dict[str, list[dict[str, Any]]]:
        """Return the full SINGLETON event log."""
        return {
            "events": [
                {"when": when, "request_id": rid, "message": msg}
                for when, rid, msg in log.all()
            ]
        }

    return app


app = create_app()
