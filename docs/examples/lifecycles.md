# Lifecycles

The three lifecycles Tripack supports - `TRANSIENT`,
`SINGLETON`, `SCOPED` - decide how often a factory is called
and how long an instance lives. Picking the right one is
usually a question of *who owns the instance* and *how
expensive is it to build*.

## At a glance

| Lifecycle | Built when | Cached on | Use it for |
| --- | --- | --- | --- |
| `TRANSIENT` | every `resolve` | nowhere | stateless helpers, value objects, throwaways |
| `SINGLETON` | first `resolve` | the resolver | expensive shared infrastructure (pools, caches) |
| `SCOPED` | first `resolve` in a scope | the active `Scope` | per-request state (sessions, transactions) |

## TRANSIENT - fresh every time

```python
from tripack_contracts import Lifecycle
from tripack_container import ContainerBuilder


class Stopwatch:
    def __init__(self) -> None:
        self.events: list[str] = []


container = (
    ContainerBuilder()
    .bind(Stopwatch, Stopwatch, lifecycle=Lifecycle.TRANSIENT)
    .build()
)
a = container.resolve(Stopwatch)
b = container.resolve(Stopwatch)
assert a is not b
```

Each resolve runs the factory. No state is shared between
two `Stopwatch` instances. This is the natural choice for
**value-like** services that hold per-call state.

`TRANSIENT` is the default lifecycle when neither the
`lifecycle=` keyword nor a provider helper (`@singleton`,
`@scoped`) is used.

## SINGLETON - one instance for the container's lifetime

```python
class CachePool:
    def __init__(self) -> None:
        self._cache: dict[str, str] = {}

    def get(self, key: str) -> str | None:
        return self._cache.get(key)


container = (
    ContainerBuilder()
    .bind(CachePool, CachePool, lifecycle=Lifecycle.SINGLETON)
    .build()
)
first = container.resolve(CachePool)
second = container.resolve(CachePool)
assert first is second
```

A `SINGLETON` is built once and reused for every subsequent
`resolve`. Its lifetime is the container's lifetime; opening
or closing scopes does not affect it.

Use `SINGLETON` for **expensive-to-build, safe-to-share**
resources: connection pools, in-memory caches, configuration
objects, loggers. Anything that holds state which **should**
be shared across the whole application.

`SINGLETON` instances exposing `close` (or `aclose`) are torn
down on `container.close()` / `aclose()` (and automatically
on `with container:` exit), in LIFO order so dependents close
before what they depend on.

## SCOPED - one instance per scope

```python
class Session:
    def __init__(self) -> None:
        self.events: list[str] = []


container = (
    ContainerBuilder()
    .bind(Session, Session, lifecycle=Lifecycle.SCOPED)
    .build()
)
with container.scope():
    first = container.resolve(Session)
    second = container.resolve(Session)
    assert first is second        # shared within the scope
with container.scope():
    other = container.resolve(Session)
    assert first is not other     # distinct across scopes
```

A `SCOPED` binding caches its instance on the active `Scope`.
Inside one `with container.scope():` block, every `resolve`
of the same token returns the same instance. Across scopes,
the instances are distinct.

Use `SCOPED` for **per-request state**: HTTP request context,
database transactions, per-job logging. The canonical pattern
is a web framework that opens one scope per inbound request,
resolves a tree of request-bound services, then closes the
scope when the response is sent.

A `SCOPED` resolve without an open scope raises `ScopeError`
- the container refuses to dangle a request-bound instance
outside its lifetime.

## SCOPED teardown

```python
class Connection:
    def __init__(self) -> None:
        self.open = True

    def close(self) -> None:
        self.open = False


container = (
    ContainerBuilder()
    .bind(Connection, Connection, lifecycle=Lifecycle.SCOPED)
    .build()
)
with container.scope():
    conn = container.resolve(Connection)
    assert conn.open is True
assert conn.open is False     # auto-closed on scope exit
```

`SCOPED` closeables are torn down when the scope exits, in
LIFO order. The container's `SINGLETON` teardowns are
independent and run on `container.close()`.

## Async lifecycles

The same three lifecycles work with async factories and
async scopes:

```python
async def make_async_pool() -> CachePool:
    return CachePool()


container = (
    ContainerBuilder()
    .bind(CachePool, make_async_pool, lifecycle=Lifecycle.SINGLETON)
    .build()
)
async with container.ascope() as scope:
    pool = await container.aresolve(CachePool)
```

`async with container.ascope():` mirrors `with
container.scope():` and awaits `aclose` on teardown targets.

## Mixing lifecycles

The lifecycles compose freely. A typical web application has:

- `SINGLETON`: connection pool, cache, config, logger.
- `SCOPED`: request, session, transaction.
- `TRANSIENT`: query builders, response formatters, anything
  stateless that needs no caching.

```python
container = (
    ContainerBuilder()
    .bind(ConnectionPool, ConnectionPool, lifecycle=Lifecycle.SINGLETON)
    .bind(Session, Session, lifecycle=Lifecycle.SCOPED)
    .bind(QueryBuilder, QueryBuilder, lifecycle=Lifecycle.TRANSIENT)
    .build()
)
```

Per request: open a scope, resolve a `Session`, resolve a
`QueryBuilder`, run business logic, exit the scope. The
`ConnectionPool` is reused across every request; the
`Session` is fresh per request; each `QueryBuilder` is fresh
per call.

## Where to go next

- [Modules](modules.md): bundle these bindings for reuse.
- Reference: [`Lifecycle`](../contracts/lifecycle.md),
  [`Container.scope`](../container/scopes.md),
  [`Container.close`](../container/teardown.md).
