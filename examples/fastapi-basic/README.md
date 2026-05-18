# FastAPI integration example

A minimal **FastAPI** service wired through a Tripack
container. Demonstrates the three canonical integration
points: bootstrapping the container in ``lifespan``, opening a
per-request scope via middleware, and adapting FastAPI's
``Depends`` to ``container.resolve``.

## What it shows

- **Lifespan bootstrap**: ``build_container()`` runs once at
  startup; ``container.aclose()`` runs once at shutdown.
- **Per-request SCOPED bindings**: a middleware opens
  ``container.ascope()`` around every HTTP request, so
  ``RequestId`` (bound as ``SCOPED``) has a fresh value per
  request without leaking across requests.
- **Generic ``Depends`` adapter**: ``from_container(token)``
  returns a callable that FastAPI introspects and invokes
  during dependency resolution; the adapter pulls the live
  container off ``request.app.state`` so route handlers
  receive Tripack-resolved instances exactly like any other
  ``Depends`` dependency.

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
```

## Testing

```bash
uv run --group dev pytest
```

The test suite uses FastAPI's ``TestClient`` and exercises:

- the SINGLETON ``Clock`` returned by ``/now``,
- per-request distinct ``RequestId`` values returned by
  ``/request-id``,
- the SINGLETON ``EventLog`` accumulating entries across
  POST ``/events``,
- isolation between two separate ``create_app()`` instances
  (each has its own container).

## File layout

```
src/fastapi_basic/
├── __init__.py        # package docstring
├── __main__.py        # `python -m fastapi_basic` entrypoint
├── services.py        # Clock / RequestId / EventLog
├── wiring.py          # build_container()
└── api.py             # lifespan, middleware, routes, Depends adapter
tests/
└── test_api.py
```

## Wiring diagram

```
        startup                request                shutdown
        =======                =======                ========

  lifespan __aenter__    ┌─ middleware __aenter__ ─┐    lifespan __aexit__
        │                │                          │            │
        v                v                          v            v
  build_container()  container.ascope()        Depends         container.aclose()
        │                │                       resolve              │
        │                │                          │            close singletons
        │                v                          v
        v          Scope.aclose            request handler runs
  app.state.container       (SCOPED teardown)
```

## Migrating to PyPI deps

When Tripack v0.1.0 ships on PyPI, drop the
``[tool.uv.sources]`` block from ``pyproject.toml`` - the
``tripack-container`` entry under ``[project] dependencies``
will then resolve against PyPI like any normal dependency.
See the parent ``../README.md`` for the full migration note.
