# ASGI primitives

`tripack_container.asgi` ships the two ASGI building blocks
every framework adapter composes. No FastAPI / Starlette
imports - the module talks the ASGI protocol directly so it
plugs into anything that follows the spec.

```python
from tripack_container.asgi import (
    container_lifespan,
    ContainerScopeMiddleware,
)
```

## `container_lifespan(app, *, container_factory)`

An `@asynccontextmanager` for the framework's `lifespan=`
keyword. Builds the container at entry, stores it on
`app.state.container` (when `app` exposes a `state`
attribute), `aclose`s it on exit.

```python
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app):
    async with container_lifespan(app, container_factory=build):
        yield
```

`container_factory` may be sync or async; the helper awaits
the result when it is awaitable. The container instance is
returned untouched - lifecycle is the only concern this
helper owns.

## `TripackMiddleware`

Base class for ASGI middleware that need
``Annotated[T, Inject]`` parameters. Subclasses define
``dispatch`` instead of ``__call__``; the base class scans the
signature once at class creation
(``__init_subclass__``) and resolves the marked parameters
from the container on every request before invoking
``dispatch``.

```python
from collections.abc import Awaitable, Callable, MutableMapping
from typing import Annotated, Any
from tripack_container import Inject
from tripack_container.asgi import TripackMiddleware


class LoggingMiddleware(TripackMiddleware):
    async def dispatch(
        self,
        scope: MutableMapping[str, Any],
        receive: Callable[[], Awaitable[MutableMapping[str, Any]]],
        send: Callable[[MutableMapping[str, Any]], Awaitable[None]],
        *,
        log: Annotated[Logger, Inject],
    ) -> None:
        log.info("request: %s", scope.get("path"))
        await self.app(scope, receive, send)
```

Per-call resolution means SCOPED tokens work **inner** to a
``ContainerScopeMiddleware``. :class:`TripackAPI` handles the
ordering automatically (subclasses added via
``app.add_middleware`` are inserted inner to the scope); in
plain Starlette / raw ASGI, place
``ContainerScopeMiddleware`` first in the middleware list so
the scope is open when ``dispatch`` runs.

A subclass that forgets to define ``dispatch`` raises
``TypeError`` at class creation (caught by
``__init_subclass__``) rather than later at first request.

## `tripack_lifespan(*, container_factory)`

Decorator factory that turns an inject-aware lifespan into a
plain one-arg lifespan compatible with any framework's
``lifespan=`` keyword:

```python
from contextlib import asynccontextmanager
from typing import Annotated
from tripack_container import Inject
from tripack_container.asgi import tripack_lifespan


@tripack_lifespan(container_factory=build_container)
@asynccontextmanager
async def lifespan(app, *, cache: Annotated[Cache, Inject]):
    await cache.warmup()
    yield
    await cache.flush()
```

The wrapper composes :func:`container_lifespan` under the
user function, then resolves the ``Annotated[T, Inject]``
keyword params from the freshly built container before
yielding control to the body. SCOPED tokens raise
:class:`tripack_contracts.ScopeError` because no scope is
active at startup - SINGLETON / TRANSIENT only.

``TripackAPI`` does the same introspection internally on its
``lifespan=`` keyword, so the decorator is only needed for
non-TripackAPI frameworks (Starlette, Litestar, raw ASGI).

## `ContainerScopeMiddleware(app, *, accessor=None)`

Pure ASGI middleware. Wraps any ASGI app; for every `http`
and `websocket` request runs the inner app inside
`container.ascope()` so SCOPED bindings cache per request.
`lifespan` scopes pass through untouched.

```python
from starlette.middleware import Middleware

app = Starlette(
    lifespan=lifespan,
    middleware=[Middleware(ContainerScopeMiddleware)],
    routes=[...],
)
```

The default accessor reads `scope['app'].state.container`,
matching what `container_lifespan` writes. Pass a custom
`accessor` callable to integrate with a framework that keeps
the container elsewhere:

```python
def accessor(scope):
    return scope["extensions"]["di_container"]


wrapped = ContainerScopeMiddleware(inner_app, accessor=accessor)
```

## API

```python
ContainerFactory = Callable[[], Container | Awaitable[Container]]
ASGIScope = MutableMapping[str, Any]
ASGIReceive = Callable[[], Awaitable[MutableMapping[str, Any]]]
ASGISend = Callable[[MutableMapping[str, Any]], Awaitable[None]]
ASGIApp = Callable[[ASGIScope, ASGIReceive, ASGISend], Awaitable[None]]
ContainerAccessor = Callable[[ASGIScope], Container]


@asynccontextmanager
async def container_lifespan(
    app: Any,
    *,
    container_factory: ContainerFactory,
) -> AsyncIterator[None]: ...


def tripack_lifespan(
    *, container_factory: ContainerFactory
) -> Callable[
    [Callable[..., AbstractAsyncContextManager[None]]],
    Callable[[Any], AbstractAsyncContextManager[None]],
]: ...


class ContainerScopeMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        *,
        accessor: ContainerAccessor | None = None,
    ) -> None: ...

    async def __call__(
        self,
        scope: ASGIScope,
        receive: ASGIReceive,
        send: ASGISend,
    ) -> None: ...


class TripackMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        *,
        accessor: ContainerAccessor | None = None,
    ) -> None: ...

    async def __call__(
        self,
        scope: ASGIScope,
        receive: ASGIReceive,
        send: ASGISend,
    ) -> None: ...

    # Subclasses define ``dispatch`` with whatever
    # ``Annotated[T, Inject]`` keyword-only parameters they
    # need; the base class scans the signature once at class
    # creation and resolves them per request.
```

## Layering

These primitives are **L2** in the three-layer Tripack
injection architecture:

```
L3  tripack_container.fastapi   - per-framework adapter (TripackAPI + Depends rewrite)
L2  tripack_container.asgi      - container_lifespan + ContainerScopeMiddleware  ← this page
L1  tripack_container._inject   - Inject marker
```

L1 is what users place in route annotations. L2 owns the
lifecycle and the per-request scope. L3 layers on top with
the framework-specific wire-up. A Starlette / Litestar
adapter would re-use L1 + L2 verbatim - only its handler
resolution mechanism would differ.

For an end-to-end Starlette walkthrough see the
[ASGI integration example](../examples/asgi.md).
