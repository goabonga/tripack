# Basic container

A first end-to-end example: instantiate a `Container`,
register a few bindings, resolve a service. All code is
copy-pasteable, framework-neutral, and demonstrates the
typical composition-root shape.

## Services

```python
class Clock:
    def now(self) -> float:
        return 1234567890.0


class Cache:
    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    def get(self, key: str) -> str | None:
        return self._store.get(key)

    def set(self, key: str, value: str) -> None:
        self._store[key] = value


class App:
    def __init__(self, clock: Clock, cache: Cache) -> None:
        self.clock = clock
        self.cache = cache

    def remember(self, key: str, value: str) -> None:
        self.cache.set(f"{self.clock.now()}:{key}", value)
```

`App` takes two collaborators by constructor. It does not
build them. That is dependency injection - applied by hand
in the next snippet, then automated by the container.

## Manual wiring (no container)

```python
clock = Clock()
cache = Cache()
app = App(clock, cache)
app.remember("user-id", "42")
```

Three lines. For a scale this small, a container is overkill -
the manual form is shorter and clearer. Use the container
when the wiring grows large enough that the construction
sequence becomes a maintenance burden.

## With the container

```python
from tripack_container import Container

container = Container()
container.bind(Clock, Clock)            # token = factory = the class itself
container.bind(Cache, Cache)
container.bind_class(App)               # auto-injects Clock and Cache

app = container.resolve(App)
app.remember("user-id", "42")
```

`container.bind(Clock, Clock)` registers the class as its own
factory: resolving `Clock` calls `Clock()` with no arguments.
`container.bind_class(App)` does the same plus inspects
`App.__init__` to auto-resolve each annotated parameter from
the container.

The container handles construction order. `resolve(App)`
recurses into `Clock` and `Cache` first, then calls
`App(clock, cache)`.

## With the builder

For a sealed container that cannot be modified after build:

```python
from tripack_container import ContainerBuilder

container = (
    ContainerBuilder()
    .bind(Clock, Clock)
    .bind(Cache, Cache)
    .bind_class(App)
    .build()
)
app = container.resolve(App)
```

The fluent chain reads top-to-bottom; `.build()` returns a
sealed `Container` whose `bind` raises `BindingError` if
called again. This is the recommended shape for application
wiring - the composition root assembles everything, then
hands off an immutable container.

## With explicit teardown

When a service needs to be closed (a file handle, a network
connection, a thread pool), the container handles the
teardown if the instance exposes a `close` (or `aclose`)
method:

```python
class ConnectionPool:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


from tripack_contracts import Lifecycle

with (
    ContainerBuilder()
    .bind(ConnectionPool, ConnectionPool, lifecycle=Lifecycle.SINGLETON)
    .build()
) as container:
    pool = container.resolve(ConnectionPool)
    assert pool.closed is False

assert pool.closed is True  # teardown ran on container exit
```

`with container:` invokes `container.close()` on exit, which
walks the SINGLETON teardown registry in LIFO order. See
[Lifecycles](lifecycles.md) for the rules per lifecycle.

## Where to go next

- [Lifecycles](lifecycles.md): when to use `TRANSIENT`,
  `SINGLETON`, or `SCOPED`.
- [Modules](modules.md): bundling bindings for reuse across
  applications.
- [Idempotent registration](idempotent-registration.md): how
  the container handles re-binds and conflicts.
- Reference: [`Container`](../container/index.md),
  [`ContainerBuilder`](../container/builder.md),
  [`bind_class`](../container/constructor-injection.md).
