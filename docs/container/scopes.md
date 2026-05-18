# Scopes

`Container.scope()` and `Container.ascope()` open a sync and an
async lifetime `Scope`. Inside a scope, `SCOPED` bindings cache
their instance for the duration of the block; on exit, every
cached closeable instance is torn down in LIFO order.

The two methods are thin convenience wrappers around the
runtime's `lifetime_scope` / `alifetime_scope` from
`docs/runtime/scopes.md`. The container method exists so users
who only import `tripack_container` have everything they need
to drive a SCOPED workflow without reaching into the runtime
module.

```python
from tripack_contracts import Lifecycle
from tripack_container import Container

container = Container()
container.bind(Request, make_request, lifecycle=Lifecycle.SCOPED)
container.bind(Logger, make_logger, lifecycle=Lifecycle.SCOPED)
```

## Sync scope

```python
with container.scope() as scope:
    handler = container.resolve(RequestHandler)
    request = container.resolve(Request)
    # `handler` and `request` share the same scope's cache.
    ...
```

Inside the `with`, `current_scope()` returns the same `Scope`
the block yields. `SCOPED` bindings cache there; on exit the
sync `close` of every registered teardown target runs in
reverse construction order. Async-only teardown targets are
skipped silently; use `ascope` for them.

## Async scope

```python
async with container.ascope() as scope:
    handler = await container.aresolve(RequestHandler)
    request = await container.aresolve(Request)
    ...
```

Same semantics, with `aclose` awaited on exit when targets
expose it (sync `close` is used as a fallback for sync-only
ones). Each `asyncio.Task` opened inside the surrounding
context inherits its own copy of the underlying `ContextVar`,
so two coroutines launched under `asyncio.gather` each open and
close their own independent scopes.

## Teardown on the error path

Both `scope` and `ascope` honor the runtime's "teardown runs
on exit even when the body raises" guarantee:

```python
try:
    with container.scope():
        container.resolve(Pool)
        raise RuntimeError("body")
except RuntimeError:
    pass
# pool.close() ran during the scope's `__exit__`, before the
# RuntimeError propagated out.
```

A teardown that itself raises is collected and surfaced as an
`ExceptionGroup` at the end - one failing target does not
prevent the others from being closed.

## Nesting

Scopes nest cleanly: the inner scope shadows the outer for its
block duration, and the outer is restored on exit. Caches are
independent:

```python
with container.scope():           # outer scope
    a = container.resolve(Cache)
    with container.scope():       # inner scope - own cache
        b = container.resolve(Cache)
    c = container.resolve(Cache)  # outer scope cache restored
# a is c, but a is not b
```

## Why this lives on the container

The runtime exposes `lifetime_scope` and `alifetime_scope` as
free functions because the runtime layer itself doesn't own a
`Container`. The container adds these methods as a discovery
convenience: a user who has a `Container` in hand can open a
scope without an extra import.
