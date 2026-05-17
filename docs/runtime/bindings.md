# Bindings

A `Binding` is the atomic registration unit the runtime stores in
its dependency graph. Each binding ties together four things:

- a **token** (the lookup key);
- a **factory** to produce instances of `T`, in synchronous OR
  asynchronous flavour (exactly one of the two);
- a **lifecycle** governing caching;
- an **auto_inject** flag, consumed by `tripack-container` to drive
  automatic constructor injection.

```python
from tripack_runtime import Binding
```

## The class

```python
@dataclass(frozen=True, slots=True)
class Binding:
    token: DependencyToken
    factory: Callable[..., Any] | None = None
    async_factory: Callable[..., Awaitable[Any]] | None = None
    lifecycle: Lifecycle = Lifecycle.TRANSIENT
    auto_inject: bool = False
```

### Why frozen + slots

- **Frozen**: once registered, a binding cannot be mutated. The
  registry can safely use it as a hash-set member, and a consumer
  receiving a binding cannot accidentally rebind a token by
  modifying the object they hold.
- **Slots**: no per-instance `__dict__`. Memory footprint matters
  because a moderately-sized container registers dozens or hundreds
  of bindings.
- **Replace**, not mutate: to "modify" an existing binding, build a
  new one via `dataclasses.replace`. The original stays untouched.

## The XOR invariant

`Binding.__post_init__` enforces that **exactly one** of `factory`
or `async_factory` is set. Both `None` is nonsensical (no way to
produce `T`); both set is ambiguous (the runtime cannot decide
which to call).

Violating the invariant raises `BindingError` at construction time,
so the mistake never propagates to a resolution attempt:

```python
from tripack_runtime import Binding

# OK: sync factory only
Binding(token=Clock, factory=Clock)

# OK: async factory only
Binding(token=AsyncClock, async_factory=make_async_clock)

# BindingError: no factory at all
Binding(token=Clock)

# BindingError: both factories provided
Binding(token=Clock, factory=Clock, async_factory=make_async_clock)
```

## Construction examples

### Sync singleton with auto-injection

```python
from tripack_contracts import Lifecycle
from tripack_runtime import Binding


class Clock:
    def __init__(self) -> None:
        self.time = "12:00:00"


binding = Binding(
    token=Clock,
    factory=Clock,
    lifecycle=Lifecycle.SINGLETON,
    auto_inject=True,
)
```

### Async scoped binding

```python
async def make_db() -> AsyncDatabase:
    db = AsyncDatabase()
    await db.connect()
    return db


binding = Binding(
    token=AsyncDatabase,
    async_factory=make_db,
    lifecycle=Lifecycle.SCOPED,
)
```

### String-keyed binding

```python
from tripack_runtime import Binding

primary = Binding(token="primary-clock", factory=Clock)
secondary = Binding(token="secondary-clock", factory=Clock)
```

The `token` field accepts any `DependencyToken`: a class, a string,
or any hashable composite (typically a tuple).

## Equality and hashing

Equality is **structural**: two bindings compare equal iff every
field matches. Hashing follows from equality, so:

```python
a = Binding(token=Clock, factory=Clock, lifecycle=Lifecycle.SINGLETON)
b = Binding(token=Clock, factory=Clock, lifecycle=Lifecycle.SINGLETON)
assert a == b
assert hash(a) == hash(b)
assert {a, b} == {a}
```

This shape lets the runtime registry detect duplicate registrations
in `O(1)` and short-circuit when an identical binding is re-applied.
Conflicting bindings (same token, different factory or lifecycle)
do **not** match and the runtime raises `BindingError` at
registration time.

## What this does NOT cover

The `Binding` type is just the data model. It carries no caching
state, no resolution machinery, no scope ownership. Those live in:

- the dependency graph (see `dependency-graph.md`),
- the resolver and its lifecycle-specific caches,
- the scope and the teardown propagation chain.

A `Binding` is created once, lives in the registry, and is read
many times by the resolver. Its immutability is what makes the
runtime's concurrency story tractable.
