# Container teardown

`Container.close()` and `Container.aclose()` tear down the
SINGLETON instances registered through the container's
resolver. The Container is also usable as a sync or async
context manager, in which case the teardown runs
automatically on `__exit__` / `__aexit__`.

```python
from tripack_container import Container

with Container() as container:
    container.bind(Pool, make_pool, lifecycle=Lifecycle.SINGLETON)
    container.resolve(Pool)
# pool.close() runs here, even if the body raised.
```

## API

```python
class Container:
    def close(self) -> None: ...
    async def aclose(self) -> None: ...

    def __enter__(self) -> Self: ...
    def __exit__(self, exc_type, exc_value, traceback) -> None: ...

    async def __aenter__(self) -> Self: ...
    async def __aexit__(self, exc_type, exc_value, traceback) -> None: ...
```

Both `close` and `aclose` delegate to the runtime's
`Resolver.close` / `Resolver.aclose`, which:

- iterate the SINGLETON teardown registry in **LIFO** order so
  dependents close before what they depend on,
- collect exceptions raised by individual targets into a
  single `ExceptionGroup` so a failing teardown does not
  prevent the others from running,
- are idempotent (a second call is a no-op via an internal
  `_closed` flag),
- skip async-only targets on the sync `close` path - reach
  them through `aclose` instead.

## SINGLETON vs SCOPED teardown

`Container.close` / `aclose` only deal with SINGLETON
teardowns. SCOPED teardowns are owned by each `Scope` opened
via `Container.scope()` / `Container.ascope()` and run on
**scope exit**, not on container exit:

```python
container = Container()
container.bind(Pool, make_pool, lifecycle=Lifecycle.SINGLETON)
container.bind(Session, make_session, lifecycle=Lifecycle.SCOPED)

with container:                       # opens the container's lifetime
    with container.scope():           # opens a request scope
        container.resolve(Session)    # SCOPED: torn down on scope exit
    container.resolve(Pool)           # SINGLETON: torn down on container exit
```

`Pool` outlives every request's `Session`; the scope's exit
closes the session, the container's exit closes the pool.

## Sync vs async path

Use the sync path when every SINGLETON in the container has a
sync ``close`` method, or when async-only targets are tolerable
to leak (the sync path skips them silently). Use the async path
when SINGLETONs include async-only ``aclose`` methods or when
the application's shutdown lives in an async context anyway.

```python
# Sync application shutdown:
with Container() as container:
    ...

# Async application shutdown:
async with Container() as container:
    ...
```

The async path falls back to sync ``close`` for sync-only
targets, so it handles mixed registries correctly.

## Combining with scopes

`Container` and `Scope` are independent context managers - they
can be nested freely:

```python
async with Container() as container:
    container.bind(Pool, make_pool, lifecycle=Lifecycle.SINGLETON)
    container.bind(Session, make_session, lifecycle=Lifecycle.SCOPED)

    async with container.ascope():
        session = await container.aresolve(Session)
    # session.aclose() ran here

    async with container.ascope():
        another = await container.aresolve(Session)
    # another.aclose() ran here

# pool.aclose() runs here, after both scopes are gone.
```
