# tripack-container

[![PyPI](https://img.shields.io/pypi/v/tripack-container.svg)](https://pypi.org/project/tripack-container/)
[![Python](https://img.shields.io/pypi/pyversions/tripack-container.svg)](https://pypi.org/project/tripack-container/)
[![CI](https://github.com/goabonga/tripack/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/goabonga/tripack/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://github.com/goabonga/tripack/blob/main/LICENSE)

High-level IoC container API of the
[Tripack](https://github.com/goabonga/tripack) framework: declarations,
wiring, modules and bootstrap helpers used by application code.

`tripack-container` is the ergonomic surface most consumers import. It is
built on top of the resolver in
[`tripack-runtime`](https://github.com/goabonga/tripack/tree/main/packages/tripack-runtime)
and the protocols defined in
[`tripack-contracts`](https://github.com/goabonga/tripack/tree/main/packages/tripack-contracts).

## Install

```bash
uv add tripack-container
# or
pip install tripack-container
```

Optional extras:

```bash
# YAML configuration loader (PyYAML)
pip install 'tripack-container[yaml]'

# FastAPI integration (TripackAPI + Inject)
pip install 'tripack-container[fastapi]'
```

## FastAPI integration

`tripack_container.fastapi` ships a drop-in `FastAPI` subclass
that owns the container lifecycle and rewrites
`Annotated[T, Inject]` parameters to FastAPI `Depends` at route
registration time.

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

Three things happen behind the scenes:

1. The container is built (sync or async factory both work) at
   lifespan startup and `aclose`d at shutdown. A user-supplied
   `lifespan=` keyword still runs, layered inside the
   container's lifecycle.
2. Every HTTP request runs inside `container.ascope()` so
   SCOPED bindings cache per-request and their teardown fires
   at request end.
3. Each `Annotated[T, Inject]` parameter is rewritten to
   `Annotated[T, Depends(...)]` at route construction time;
   FastAPI's own dependency system then resolves `T` from
   `app.state.container` per request. `app.dependency_overrides`
   continues to work for tests.

### The `Inject` marker

| Form | Meaning |
| --- | --- |
| `Annotated[T, Inject]` | Resolve `T` from the container; raise on miss. |
| `Annotated[T \| None, Inject]` | Resolve `T`; return `None` if unbound (implicit optional from the union). |
| `Annotated[T, Inject(optional=True)]` | Same as the union form, explicit flag. |
| `Annotated[T, Inject(token="named")]` | Override the resolution token (named bindings). |

### Sub-routers: `TripackRouter`

Sub-routers built with the default `APIRouter` analyse their
routes at decoration time, before `app.include_router` runs,
and crash on the bare `Inject` marker. Use `TripackRouter`
instead - it defaults its `route_class` to the inject-aware
variant:

```python
from tripack_container.fastapi import TripackRouter

sub = TripackRouter(prefix="/v2")


@sub.get("/now")
def v2_now(clock: Annotated[Clock, Inject]) -> dict[str, float]:
    return {"now": clock.now()}


app.include_router(sub)
```

### Architecture: three layers, one marker

```
Layer 3 (per-framework adapter)  tripack_container.fastapi   - TripackAPI subclass
Layer 2 (ASGI-agnostic)          tripack_container.asgi      - container_lifespan
                                                              + ContainerScopeMiddleware
Layer 1 (framework-agnostic)     tripack_container._inject   - Inject marker
```

- **Layer 1 - `Inject` marker.** A pure data class. No
  ASGI, no FastAPI, no Starlette. Every adapter reads it the
  same way through `parse_inject(annotation)`.
- **Layer 2 - ASGI primitives.** `container_lifespan` is an
  `@asynccontextmanager` you can plug into any framework that
  accepts a lifespan (Starlette, FastAPI, Litestar, raw ASGI).
  `ContainerScopeMiddleware` is a pure ASGI middleware that
  opens `container.ascope()` per HTTP/WebSocket request. Test
  coverage includes a Starlette-only path that wires both
  primitives without importing FastAPI.
- **Layer 3 - FastAPI adapter.** `TripackAPI` composes the
  ASGI layer and adds the FastAPI-specific concern (rewriting
  `Annotated[T, Inject]` to `Depends`). A Starlette adapter
  would be a similar L3 module that re-uses L1 + L2 verbatim
  and adds its own route-level resolution mechanism.

The subclass choice for `TripackAPI` (rather than composite)
is documented in the module docstring; the headline is that
subclassing keeps `isinstance(app, FastAPI)` truthy so every
FastAPI tool (`TestClient`, deployment runners,
`app.dependency_overrides`) keeps working untouched while the
constructor surface mirrors `FastAPI(...)`.

### Other ASGI frameworks (Starlette, Litestar, raw ASGI)

The L2 primitives - `container_lifespan` +
`ContainerScopeMiddleware` - work without FastAPI. The
[ASGI integration guide](https://goabonga.github.io/tripack/examples/asgi.html)
ships the Starlette and raw-ASGI wiring templates plus the
custom-`accessor` recipe for frameworks that keep app state
outside `app.state`. Handlers there resolve from
`request.app.state.container` manually - the
`Annotated[T, Inject]` rewriting in L3 is the only piece
that is FastAPI-specific.

## Documentation

Project site: <https://goabonga.github.io/tripack/>.

## License

MIT - see [LICENSE](https://github.com/goabonga/tripack/blob/main/LICENSE).
