# ASGI integration

Tripack ships two framework-agnostic ASGI primitives in
[`tripack_container.asgi`](https://github.com/goabonga/tripack/blob/main/packages/tripack-container/src/tripack_container/asgi.py).
They handle the two concerns every ASGI framework needs for
DI: lifecycle (build at startup, close at shutdown) and
per-request scope (a fresh cache for SCOPED bindings).

Neither primitive imports FastAPI. They work as-is with
Starlette, Litestar, raw ASGI apps, or any other framework
that follows the ASGI spec.

## The two primitives

### `container_lifespan(app, *, container_factory)`

An `@asynccontextmanager` you plug into the framework's
`lifespan=` keyword. It:

1. Calls `container_factory()` (sync or async - awaits if
   awaitable) at entry.
2. Stores the container on `app.state.container` when `app`
   exposes a `state` attribute (Starlette / FastAPI
   convention).
3. Yields control to the framework / user lifespan.
4. Calls `container.aclose()` on exit so SINGLETON teardown
   targets release in LIFO order.

### `ContainerScopeMiddleware(app, *, accessor=None)`

A pure ASGI middleware that opens `container.ascope()` around
every `http` and `websocket` request. `lifespan` messages
pass through untouched - they belong to `container_lifespan`,
not the middleware. The container is read from
`scope['app'].state.container` by default; pass a custom
`accessor` callable if your framework keeps it elsewhere.

## Pure Starlette

```python
from contextlib import asynccontextmanager
from typing import Annotated

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.responses import JSONResponse
from starlette.routing import Route

from tripack_container import Inject
from tripack_container.asgi import (
    ContainerScopeMiddleware,
    TripackMiddleware,
    container_lifespan,
    tripack_lifespan,
)


@tripack_lifespan(container_factory=build_container)
@asynccontextmanager
async def lifespan(
    app,
    *,
    cache: Annotated[Cache, Inject],   # resolved at startup
):
    await cache.warmup()
    yield


class StampMiddleware(TripackMiddleware):
    async def dispatch(
        self, scope, receive, send,
        *,
        log: Annotated[Logger, Inject],   # resolved per request
    ):
        log.info("request received")
        await self.app(scope, receive, send)


async def now(request):
    # No FastAPI Depends in Starlette; route handlers resolve
    # the container themselves.
    container = request.app.state.container
    clock = await container.aresolve(Clock)
    return JSONResponse({"now": clock.now()})


app = Starlette(
    lifespan=lifespan,
    middleware=[
        Middleware(ContainerScopeMiddleware),   # outer - opens scope
        Middleware(StampMiddleware),            # inner - sees scope
    ],
    routes=[Route("/now", now)],
)
```

Two of the three injection sites - lifespan and middleware -
use the same ``Annotated[T, Inject]`` syntax as in TripackAPI:
``tripack_lifespan`` and ``TripackMiddleware`` both introspect
the signature and resolve from the container.

The only thing Starlette is missing is the per-route
rewriting: route handlers must resolve from the container
manually (the canonical Starlette idiom).

## Raw ASGI (no framework)

For a pure ASGI app the same two primitives compose directly:

```python
import contextlib

container = None


async def app(scope, receive, send):
    """Pure ASGI: route on scope['type'] + dispatch."""
    if scope["type"] == "http" and scope["path"] == "/now":
        clock = await scope["state"]["container"].aresolve(Clock)
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({
            "type": "http.response.body",
            "body": f'{{"now": {clock.now()}}}'.encode(),
        })


# Lifespan management is decoupled from middleware - here we
# attach it via an outer wrapper rather than the framework's
# lifespan= keyword (raw ASGI has no such keyword).
async def with_lifecycle(scope, receive, send):
    global container
    if scope["type"] == "lifespan":
        async with container_lifespan(
            scope,  # any namespace with a ``state`` attribute will do
            container_factory=build_container,
        ):
            while True:
                message = await receive()
                if message["type"] == "lifespan.startup":
                    await send({"type": "lifespan.startup.complete"})
                elif message["type"] == "lifespan.shutdown":
                    await send({"type": "lifespan.shutdown.complete"})
                    return
        return
    await ContainerScopeMiddleware(app, accessor=lambda _: container)(
        scope, receive, send
    )
```

In practice nobody writes their app this way - Starlette /
FastAPI / Litestar handle the lifespan handshake for you. The
example exists to show that the primitives carry no framework
assumption.

## Custom accessor

The default accessor reads `scope['app'].state.container`,
which matches what `container_lifespan` writes. Frameworks
that keep app state elsewhere can pass a custom callable:

```python
def accessor(scope):
    # e.g. a Litestar-shaped scope:
    return scope["state"]["di_container"]


app = ContainerScopeMiddleware(inner_app, accessor=accessor)
```

The accessor receives the ASGI scope mapping and returns a
`Container` instance. The middleware never assumes any
storage convention beyond what the accessor returns.

## Test coverage

The standalone Starlette + raw ASGI paths are exercised by
[`packages/tripack-container/tests/test_container_asgi.py`](https://github.com/goabonga/tripack/blob/main/packages/tripack-container/tests/test_container_asgi.py)
- the test module never imports FastAPI, so a regression in
the framework-agnostic claim would fail there immediately.

## Where to go from here

- [FastAPI integration](fastapi.md) - the ergonomic L3
  adapter (`TripackAPI` + `Annotated[T, Inject]` rewriting)
  built on top of these primitives.
- [Container builder](../container/builder.md) - the
  underlying `ascope()` / `aclose` semantics these helpers
  compose around.
