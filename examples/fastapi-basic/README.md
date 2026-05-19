# FastAPI integration example

A minimal **FastAPI** service wired through a Tripack
container. Demonstrates the recommended integration shape:

- the application is a [`TripackAPI`](https://github.com/goabonga/tripack/blob/main/packages/tripack-container/src/tripack_container/fastapi.py) (FastAPI subclass) that owns the container lifecycle;
- bindings are declared in a JSON file (`container.json`)
  rather than Python code;
- handlers receive their dependencies through
  `Annotated[T, Inject]` parameters - no `Depends` boilerplate;
- the example shows **simple**, **optional (`T | None`)**, and
  **chained-interface** injection in one place.

## What it shows

- **Declarative wiring**: the entire container is built from
  `container.json` via `load_json`. No Python wiring file -
  configuration is data.
- **Interface-driven handlers**: handlers reference the
  `Protocol`s in `contracts.py` (`Clock`, `EventLog`,
  `AuditTrail`, ...) and never import the concrete classes from
  `services.py`. Swapping an implementation is a one-line
  change in the JSON.
- **`Annotated[T, Inject]` resolution**: the
  `TripackAPI`-aware route class rewrites injection sites to
  FastAPI `Depends` at registration time, so FastAPI's own
  dependency system runs the resolution under the per-request
  scope opened by the middleware. OpenAPI stays clean - the
  injected services do not appear in the schema.
- **Optional dependencies**: `Annotated[Notifier | None, Inject]`
  returns `None` when no binding exists. The `Notifier`
  interface has no entry in `container.json`, so `/notify`
  reports `delivered: false` instead of raising.
- **Chained interfaces**: `AuditTrail` is itself a `Protocol`,
  bound to `DefaultAuditTrail` with `auto_inject=true`. The
  default impl takes `Clock` and `EventLog` (both interfaces)
  in its `__init__` and the container resolves them
  automatically.

## Running

```bash
cd examples/fastapi-basic
uv sync
uv run python -m fastapi_basic
# -> Uvicorn running on http://127.0.0.1:8000
```

Then in another shell:

```bash
curl http://127.0.0.1:8000/now
curl http://127.0.0.1:8000/request-id    # uuid1
curl http://127.0.0.1:8000/request-id    # uuid2 (different - SCOPED)
curl -X POST 'http://127.0.0.1:8000/events?message=hello'
curl -X POST 'http://127.0.0.1:8000/events?message=world'
curl http://127.0.0.1:8000/events
curl -X POST http://127.0.0.1:8000/audit/login
curl http://127.0.0.1:8000/notify/hello-world      # delivered=false
```

## Testing

```bash
uv run --group dev pytest
```

The test suite uses FastAPI's `TestClient` and exercises:

- SINGLETON `Clock` resolved via `Annotated[Clock, Inject]`,
- per-request distinct `RequestId` (SCOPED),
- SINGLETON `EventLog` accumulating entries,
- per-app isolation (each `TripackAPI` gets its own container),
- chained-interface injection via `AuditTrail` +
  `auto_inject`,
- optional injection via `Annotated[Notifier | None, Inject]`
  returning `None`.

## File layout

```
src/fastapi_basic/
├── __init__.py          # package docstring
├── __main__.py          # `python -m fastapi_basic` entrypoint
├── contracts.py         # Protocols (Clock, RequestId, EventLog, AuditTrail, Notifier)
├── services.py          # Concrete impls (SystemClock, Uuid4RequestId, ...)
├── container.json       # Declarative bindings: interface -> impl
└── api.py               # TripackAPI + routes (no manual lifespan/middleware)
tests/
└── test_api.py
```

## Wiring shape

```
            startup                request                shutdown
            =======                =======                ========

  TripackAPI lifespan opens   per-request middleware     lifespan closes
            │                  opens container.ascope()        │
            v                          │                       v
     load_json(container.json)         v                container.aclose()
            │                  Depends-rewritten              │
            v                  Annotated[T, Inject]      SINGLETON
     app.state.container       resolves T from           teardown
                               container                 in LIFO order
                                       │
                                       v
                               handler runs inside scope
                               (SCOPED bindings cache here)
```

## Why `TripackAPI` as a subclass of `FastAPI`

The design choice is documented in the
[`tripack_container.fastapi` module
docstring](https://github.com/goabonga/tripack/blob/main/packages/tripack-container/src/tripack_container/fastapi.py).
Short version: subclassing keeps `isinstance(app, FastAPI)`
truthy so every FastAPI tool (TestClient, deployment runners,
Starlette middlewares) continues to work unchanged, while the
ergonomic surface of `TripackAPI(container_factory=...)`
matches `FastAPI(...)` one-for-one.
