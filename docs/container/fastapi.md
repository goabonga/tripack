# FastAPI adapter

`tripack_container.fastapi` is the L3 adapter that turns the
core Tripack container into a drop-in FastAPI experience.
Three public symbols:

```python
from tripack_container import Inject  # L1 marker (re-exported at top level)
from tripack_container.fastapi import TripackAPI, TripackRouter
```

Plus an optional extra so the dependency stays opt-in:

```bash
pip install 'tripack-container[fastapi]'
```

## `Inject`

The marker for `Annotated[T, Inject]` parameters in route
handlers. Supports four forms:

| Annotation | Meaning |
| --- | --- |
| `Annotated[T, Inject]` | Resolve `T` from the container; raise on miss. |
| `Annotated[T \| None, Inject]` | Resolve `T`; return `None` if unbound. |
| `Annotated[T, Inject(optional=True)]` | Explicit optional flag (same effect as the `\| None` union). |
| `Annotated[T, Inject(token="named")]` | Resolve a named token instead of `T`. |

The marker is L1 (framework-agnostic); `TripackAPI` is the L3
adapter that gives it meaning inside a FastAPI route.

## `TripackAPI`

A `FastAPI` subclass that takes a `container_factory` and
wires everything else automatically:

- container build at lifespan startup, `aclose` at shutdown
  (delegated to `container_lifespan` from
  [`tripack_container.asgi`](asgi.md));
- per-request `container.ascope()` via
  `ContainerScopeMiddleware`;
- `Annotated[T, Inject]` parameters on every route rewritten
  to `Annotated[T, Depends(...)]` so FastAPI's own
  dependency machinery resolves the token.

```python
from typing import Annotated, Protocol

from tripack_container import Inject
from tripack_container.fastapi import TripackAPI
from tripack_container.loaders import load_json


class Clock(Protocol):
    def now(self) -> float: ...


app = TripackAPI(container_factory=lambda: load_json("container.json"))


@app.get("/now")
def now(clock: Annotated[Clock, Inject]) -> dict[str, float]:
    return {"now": clock.now()}
```

A user-supplied `lifespan=` keyword still runs - it is
composed inside the container lifecycle, so user-startup code
can already read `app.state.container`. The same
`Annotated[T, Inject]` syntax that handlers use also works on
the lifespan signature: `TripackAPI` introspects it at
startup and resolves the marked keyword parameters from the
freshly built container before invoking the user lifespan:

```python
@asynccontextmanager
async def lifespan(
    app: FastAPI,
    *,
    cache: Annotated[Cache, Inject],
) -> AsyncIterator[None]:
    await cache.warmup()
    yield


app = TripackAPI(container_factory=build, lifespan=lifespan)
```

SCOPED tokens are not resolvable at startup (no scope is
active) - SINGLETON / TRANSIENT only. The introspection is
identical to the one [`tripack_lifespan`](asgi.md) provides
for non-TripackAPI frameworks; TripackAPI just does it
automatically.

### Middleware injection: `TripackMiddleware`

For middleware that needs to resolve from the container per
request, subclass [`TripackMiddleware`](asgi.md). The same
`Annotated[T, Inject]` keyword-only syntax applies on the
`dispatch` method:

```python
from tripack_container.asgi import TripackMiddleware


class RequestStampMiddleware(TripackMiddleware):
    async def dispatch(
        self, scope, receive, send,
        *,
        log: Annotated[EventLog, Inject],
        rid: Annotated[RequestId, Inject],
    ) -> None:
        log.record(0, rid.value, f"middleware:{scope['path']}")
        await self.app(scope, receive, send)


app.add_middleware(RequestStampMiddleware)
```

`TripackAPI.add_middleware` detects `TripackMiddleware`
subclasses and inserts them **inner** to
`ContainerScopeMiddleware` so SCOPED tokens (like
`RequestId` above) are resolvable. Non-Tripack middleware
keep the standard outer placement.

## `TripackRouter`

An `APIRouter` subclass whose `route_class` defaults to the
inject-aware variant. Required for sub-routers that use
`Annotated[T, Inject]` - the default `APIRouter` analyses its
endpoints at decoration time (before `include_router` runs)
and rejects the bare `Inject` marker as a non-Pydantic field.

```python
from tripack_container.fastapi import TripackRouter

sub = TripackRouter(prefix="/v2")


@sub.get("/now")
def v2_now(clock: Annotated[Clock, Inject]) -> dict[str, float]:
    return {"now": clock.now()}


app.include_router(sub)
```

`TripackAPI.include_router` also promotes a default
`APIRouter` to the inject-aware route class - safe net for
sub-routers that happen not to use `Inject` today but might
later.

## Design choice: subclass over composite

`TripackAPI` is a **subclass** of `FastAPI`, not a composite
holding a `FastAPI` instance. The trade-offs:

| Pattern | Pro | Con |
| --- | --- | --- |
| **Subclass** *(chosen)* | `isinstance(app, FastAPI)` stays truthy; every FastAPI tool keeps working. Constructor surface matches `FastAPI(...)`. | Tight coupling to FastAPI internals. |
| Composite (`app.fastapi`) | Loose coupling. | Breaks ASGI app expectations; every consumer needs `.fastapi` indirection. |
| Function (`bind_container(app, ...)`) | Works with any user subclass. | Lifespan composition is awkward - FastAPI fixes the lifespan at construction. |

The L1 marker and the L2 ASGI primitives are framework-agnostic;
the subclass coupling is intentional and confined to this L3
module.

## API

```python
class TripackAPI(FastAPI):
    def __init__(
        self,
        *args: Any,
        container_factory: ContainerFactory,
        **kwargs: Any,
    ) -> None: ...

    def include_router(
        self,
        router: APIRouter,
        *args: Any,
        **kwargs: Any,
    ) -> None: ...


class TripackRouter(APIRouter):
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...
```

For an end-to-end walkthrough (JSON wiring, interface-driven
handlers, optional dependencies, chained interfaces) see the
[FastAPI integration example](../examples/fastapi.md).
