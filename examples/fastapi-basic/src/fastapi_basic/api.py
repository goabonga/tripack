# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""FastAPI application driven by ``TripackAPI`` + JSON container config.

The whole wiring is a single line in ``TripackAPI(container_factory=...)``:

- the container is loaded from :file:`container.json` (declarative
  binding of interface tokens to concrete factories);
- the container's lifecycle is owned by the FastAPI lifespan;
- each request runs inside ``container.ascope()`` so SCOPED
  bindings cache per request;
- parameters annotated ``Annotated[T, Inject]`` resolve from
  the container, with optional ``T | None`` support for
  bindings that may be absent.

The same ``Annotated[T, Inject]`` syntax extends to two more
sites:

- the **user lifespan** keyword params are auto-introspected
  by ``TripackAPI`` and resolved at startup
  (``app_lifespan`` below);
- a **TripackMiddleware** subclass resolves its ``dispatch``
  keyword params per request (``RequestStampMiddleware``
  below).

Handlers, middleware, and lifespan all reference **interfaces**
(``Clock``, ``EventLog``, ``AuditTrail``, ...) - never the
concrete classes from ``services.py`` - so swapping
implementations is a config-only change with no Python rewrite.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI

from fastapi_basic.contracts import AuditTrail, Clock, EventLog, Notifier, RequestId
from tripack_container import Inject
from tripack_container.asgi import ASGIReceive, ASGIScope, ASGISend, TripackMiddleware
from tripack_container.fastapi import TripackAPI
from tripack_container.loaders import load_json

# Resolved once at import time so the lifespan factory below has
# a stable path regardless of the process' working directory.
CONFIG_PATH = Path(__file__).parent / "container.json"


def build_container() -> Any:
    """Container factory invoked by ``TripackAPI`` at lifespan startup.

    Wraps ``load_json`` in a no-arg callable so the factory
    closure is independent of where the file lives - useful for
    test setups that pass an alternative ``container_factory``
    pointing at a different JSON.
    """
    return load_json(CONFIG_PATH)


@asynccontextmanager
async def app_lifespan(
    app: FastAPI,
    *,
    clock: Annotated[Clock, Inject],
    log: Annotated[EventLog, Inject],
) -> AsyncIterator[None]:
    """Inject-aware lifespan: same ``Annotated[T, Inject]`` syntax as handlers.

    ``TripackAPI`` introspects this signature once at startup
    and resolves ``clock`` + ``log`` from the freshly-built
    container before entering the body. SCOPED tokens would
    raise :class:`tripack_contracts.ScopeError` here (no scope
    is active at startup) - SINGLETON / TRANSIENT only.
    """
    log.record(clock.now(), "_lifespan", "startup")
    try:
        yield
    finally:
        log.record(clock.now(), "_lifespan", "shutdown")


class RequestStampMiddleware(TripackMiddleware):
    """Stamp every HTTP request in the :class:`EventLog`.

    Demonstrates per-request injection on a middleware: each
    call to ``dispatch`` resolves ``clock``, ``rid``, ``log``
    from the active scope **before** the route handler runs.
    The middleware never imports the concrete implementations -
    only the interfaces from :mod:`fastapi_basic.contracts`.
    """

    async def dispatch(
        self,
        scope: ASGIScope,
        receive: ASGIReceive,
        send: ASGISend,
        *,
        clock: Annotated[Clock, Inject],
        rid: Annotated[RequestId, Inject],
        log: Annotated[EventLog, Inject],
    ) -> None:
        """Log a middleware-stamped entry, forward to the inner app."""
        log.record(clock.now(), rid.value, f"middleware:{scope['path']}")
        await self.app(scope, receive, send)


app = TripackAPI(container_factory=build_container, lifespan=app_lifespan)
app.add_middleware(RequestStampMiddleware)


@app.get("/now")
def now(clock: Annotated[Clock, Inject]) -> dict[str, float]:
    """SINGLETON clock injection - one instance for the whole process."""
    return {"now": clock.now()}


@app.get("/request-id")
def request_id(rid: Annotated[RequestId, Inject]) -> dict[str, str]:
    """SCOPED injection - a fresh ``RequestId`` per HTTP request."""
    return {"request_id": rid.value}


@app.post("/events")
def append_event(
    message: str,
    clock: Annotated[Clock, Inject],
    rid: Annotated[RequestId, Inject],
    log: Annotated[EventLog, Inject],
) -> dict[str, Any]:
    """Record an entry combining a SINGLETON, a SCOPED and a SINGLETON token."""
    log.record(clock.now(), rid.value, message)
    return {"count": len(log.all()), "request_id": rid.value}


@app.get("/events")
def list_events(log: Annotated[EventLog, Inject]) -> dict[str, list[dict[str, Any]]]:
    """Read back the SINGLETON event log - shared across requests."""
    return {
        "events": [
            {"when": when, "request_id": rid, "message": msg}
            for when, rid, msg in log.all()
        ]
    }


@app.post("/audit/{action}")
def audit(
    action: str,
    rid: Annotated[RequestId, Inject],
    trail: Annotated[AuditTrail, Inject],
    log: Annotated[EventLog, Inject],
) -> dict[str, object]:
    """Chained-interface injection.

    ``AuditTrail`` is itself a ``Protocol`` bound to
    ``DefaultAuditTrail`` with ``auto_inject=true`` - so the
    runtime constructs ``DefaultAuditTrail`` by resolving its
    constructor's interface parameters (``Clock``,
    ``EventLog``) from the container. The handler stays
    oblivious to that chain.
    """
    trail.trace(rid.value, action)
    return {"audited": action, "entries": len(log.all())}


@app.get("/notify/{message}")
def notify(
    message: str,
    notifier: Annotated[Notifier | None, Inject],
) -> dict[str, object]:
    """Optional injection.

    ``Notifier`` has no binding in :file:`container.json`. The
    ``T | None`` annotation tells :class:`Inject` to return
    ``None`` instead of raising; the handler degrades
    gracefully when the dependency is absent.
    """
    if notifier is None:
        return {"delivered": False, "message": message}
    notifier.notify(message)
    return {"delivered": True, "message": message}
