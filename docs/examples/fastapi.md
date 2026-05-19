# FastAPI integration

Tripack ships a first-class FastAPI adapter:
[`tripack_container.fastapi`](https://github.com/goabonga/tripack/blob/main/packages/tripack-container/src/tripack_container/fastapi.py).
It exposes two symbols a handler module imports - `TripackAPI`
and `Inject` - and rewrites every `Annotated[T, Inject]`
parameter to FastAPI's own `Depends` mechanism at route
registration time.

The runnable counterpart of this guide lives at
[`examples/fastapi-basic`](https://github.com/goabonga/tripack/tree/main/examples/fastapi-basic).

The FastAPI adapter sits on top of the framework-agnostic
[ASGI primitives](asgi.md) (`container_lifespan` +
`ContainerScopeMiddleware`). If you target Starlette or raw
ASGI, jump straight to that page - the marker described below
still applies, only the route-level rewriting is FastAPI-specific.

## Minimal app

```python
from pathlib import Path
from typing import Annotated, Protocol

from tripack_container import Inject
from tripack_container.fastapi import TripackAPI
from tripack_container.loaders import load_json


class Clock(Protocol):
    def now(self) -> float: ...


app = TripackAPI(
    container_factory=lambda: load_json(Path("container.json")),
)


@app.get("/now")
def now(clock: Annotated[Clock, Inject]) -> dict[str, float]:
    return {"now": clock.now()}
```

`container.json`:

```json
{
  "bindings": [
    {
      "token": "myapp.contracts.Clock",
      "factory": "myapp.services.SystemClock",
      "lifecycle": "singleton"
    }
  ]
}
```

That is the entire wiring. The container is built at
lifespan startup, `aclose`d at shutdown, and every HTTP
request runs inside `container.ascope()` so SCOPED bindings
cache per request.

## Forms of injection

| Annotation form | Behaviour |
| --- | --- |
| `Annotated[T, Inject]` | Resolve `T` from the container; raise on miss. |
| `Annotated[T \| None, Inject]` | Resolve `T`; return `None` if no binding (optional). |
| `Annotated[T, Inject(optional=True)]` | Explicit optional flag (same as the union form). |
| `Annotated[T, Inject(token="primary")]` | Resolve the named token instead of `T`. |

The same syntax works on three sites: route handlers
(unchanged), the **user lifespan** (`TripackAPI` introspects
the signature and resolves kwargs at startup), and
**`TripackMiddleware`** subclasses (`dispatch` kwargs resolved
per request). No decorator at the user level - the framework
adapter handles the introspection.

## Interfaces over concretes

Handlers reference [`Protocol`](https://docs.python.org/3/library/typing.html#typing.Protocol)s
defined in a `contracts.py` module; `container.json` binds
each interface to a concrete implementation. Swapping
implementations is a config-only change:

```json
{
  "token": "myapp.contracts.Clock",
  "factory": "myapp.services.FrozenClock",
  "lifecycle": "singleton"
}
```

The handler module never imports `SystemClock` or
`FrozenClock` - only `Clock`.

## Chained interfaces with `auto_inject`

A service that depends on **other interfaces** declares them
as constructor parameters and binds with `auto_inject: true`.
The container inspects the constructor at resolution time and
fills the interface arguments from the other bindings:

```python
class AuditTrail(Protocol):
    def trace(self, request_id: str, action: str) -> None: ...


class DefaultAuditTrail:
    def __init__(self, clock: Clock, log: EventLog) -> None:
        self._clock, self._log = clock, log

    def trace(self, request_id: str, action: str) -> None:
        self._log.record(self._clock.now(), request_id, f"audit:{action}")
```

```json
{
  "token": "myapp.contracts.AuditTrail",
  "factory": "myapp.services.DefaultAuditTrail",
  "lifecycle": "singleton",
  "auto_inject": true
}
```

The handler still only writes `Annotated[AuditTrail, Inject]` -
the chain through `Clock` and `EventLog` is internal to the
implementation.

## Sub-routers: `TripackRouter`

The default `APIRouter` analyses its routes when `@router.get`
fires, before `app.include_router` runs. It crashes on the
bare `Inject` marker because FastAPI tries to interpret it as
a Pydantic field. Use `TripackRouter` instead:

```python
from tripack_container.fastapi import TripackRouter

sub = TripackRouter(prefix="/v2")


@sub.get("/now")
def v2_now(clock: Annotated[Clock, Inject]) -> dict[str, float]:
    return {"now": clock.now()}


app.include_router(sub)
```

`TripackRouter` defaults its `route_class` to the inject-aware
variant so the rewrite happens at registration time.

## Testing

`TripackAPI` is a `FastAPI` subclass, so the regular
`TestClient` + `app.dependency_overrides` workflow keeps
working. For container-level overrides, swap the factory:

```python
def test_with_frozen_clock():
    app = TripackAPI(
        container_factory=lambda: load_json(Path("container.test.json")),
    )
    # ... register routes, drive client
```

The `container.test.json` binds `Clock` to a `FrozenClock`
impl; everything else stays identical.

## Architecture and design choice

The integration is split into three layers so the framework
coupling stays at the edge:

```
Layer 3 (per-framework adapter)  tripack_container.fastapi   - TripackAPI
Layer 2 (ASGI-agnostic)          tripack_container.asgi      - container_lifespan
                                                              + ContainerScopeMiddleware
Layer 1 (framework-agnostic)     tripack_container._inject   - Inject marker
```

- **L1** ships the marker. No ASGI, no FastAPI, no Starlette.
- **L2** ships the lifecycle: `container_lifespan` (an
  `@asynccontextmanager` any ASGI framework can use as
  `lifespan=`) and `ContainerScopeMiddleware` (pure ASGI
  middleware opening `ascope()` per request).
- **L3** adds the FastAPI-specific concern: rewriting
  `Annotated[T, Inject]` to `Depends(...)` so FastAPI's own
  dependency machinery resolves the token. Test coverage
  includes a Starlette-only path that uses L1 + L2 without
  importing FastAPI, proving the lower layers really are
  framework-agnostic.

Within L3, `TripackAPI` is a **subclass** of `FastAPI`, not a
composite. The alternatives:

| Pattern | Pro | Con |
| --- | --- | --- |
| **Subclass** *(chosen)* | `isinstance(app, FastAPI)` stays truthy - every FastAPI tool keeps working unchanged. Ergonomic surface matches `FastAPI(...)`. | Tight coupling to FastAPI internals. |
| Composite (`app.fastapi`) | Loose coupling. | Breaks ASGI app expectations; every consumer needs the `.fastapi` indirection. |
| Function (`bind_container(app, ...)`) | Works with any FastAPI variant or user subclass. | Doesn't address the lifespan composition cleanly (FastAPI fixes the lifespan at construction). |

A future Starlette, Litestar or pure-ASGI L3 adapter would
re-use L1 + L2 verbatim and only differ in how it surfaces
parameter resolution to handlers.

## Inject everywhere: handler + lifespan + middleware

The end-to-end pattern in one block:

```python
from contextlib import asynccontextmanager
from typing import Annotated

from tripack_container import Inject
from tripack_container.asgi import TripackMiddleware
from tripack_container.fastapi import TripackAPI


@asynccontextmanager
async def lifespan(
    app,
    *,
    cache: Annotated[Cache, Inject],   # resolved at startup
) -> None:
    await cache.warmup()
    yield


class StampMiddleware(TripackMiddleware):
    async def dispatch(
        self, scope, receive, send,
        *,
        log: Annotated[Logger, Inject],   # resolved per request
    ) -> None:
        log.info("request received")
        await self.app(scope, receive, send)


app = TripackAPI(container_factory=build, lifespan=lifespan)
app.add_middleware(StampMiddleware)   # auto-inserted INNER to scope


@app.get("/now")
def now(clock: Annotated[Clock, Inject]) -> dict[str, float]:   # resolved per request
    return {"now": clock.now()}
```

Three injection sites, one syntax. The user never imports
``@inject`` or any decorator; ``TripackAPI`` does the
introspection in three places (route signatures via the route
class, lifespan signature via ``_compose_lifespan``, middleware
``dispatch`` via ``__init_subclass__``).

## Other ASGI frameworks

For Starlette, raw ASGI, or any other framework that follows
the ASGI spec, use the L2 primitives directly - see the
[ASGI integration](asgi.md) guide for the Starlette and raw
ASGI templates. Same lifecycle and per-request scope, only
the **route**-level `Annotated[T, Inject]` rewriting is
FastAPI-specific: ``TripackMiddleware`` and
``tripack_lifespan`` work identically in any ASGI framework.
