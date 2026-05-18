# Container builder

`ContainerBuilder` is the fluent factory for sealed
`Container` instances. The idiomatic way to wire a Tripack
application is: build a `ContainerBuilder`, register bindings
through `bind` chains (and later `install` for modules,
loaders for TOML/JSON/YAML config), then materialise the
wiring through `build()`. The returned `Container` is
**sealed** - any further `Container.bind` call raises
`BindingError`.

```python
from tripack_contracts import Lifecycle
from tripack_container import ContainerBuilder

container = (
    ContainerBuilder()
    .bind(Clock, make_clock, lifecycle=Lifecycle.SINGLETON)
    .bind(Cache, make_cache, lifecycle=Lifecycle.SCOPED)
    .bind(Logger, make_logger)
    .build()
)

clock = container.resolve(Clock)
```

## API

```python
class ContainerBuilder:
    def __init__(self) -> None: ...

    @overload
    def bind[T](
        self,
        token: type[T],
        factory: Callable[..., T],
        *,
        lifecycle: Lifecycle = Lifecycle.TRANSIENT,
        auto_inject: bool = False,
    ) -> Self: ...

    @overload
    def bind[T](
        self,
        token: type[T],
        factory: Callable[..., Awaitable[T]],
        *,
        lifecycle: Lifecycle = Lifecycle.TRANSIENT,
        auto_inject: bool = False,
    ) -> Self: ...

    def build(self) -> Container: ...
```

`bind` returns `Self` so calls can be chained. The signature,
auto-detection of sync vs async, idempotent re-bind semantics
and conflict-at-bind-time guarantees are the same as
`Container.bind` (see [`bindings.md`](bindings.md)).

## Sealing

`build()` does three things:

1. snapshots the accumulated bindings into a fresh
   `DependencyGraph`;
2. hands that graph to a new `Container`;
3. calls the internal `_seal` on the container so any
   subsequent `Container.bind` raises `BindingError`.

The sealing makes the produced container immutable in its
wiring; the resolver still mutates its singleton cache and
teardown registry as it runs, but the set of bindings is
frozen for the container's lifetime.

```python
container = ContainerBuilder().bind(Clock, make_clock).build()
container.bind(Cache, make_cache)
# -> BindingError: Container is sealed; bindings can no longer be added
#    after ContainerBuilder.build(). Re-build from a new builder to
#    extend the wiring.
```

## Independent rebuilds

The builder remains mutable after `build()`, so the same
instance can produce many independent containers. Each `build`
snapshots the graph, so a later `bind` on the builder does NOT
affect already-built containers:

```python
builder = ContainerBuilder().bind(Clock, make_clock)
first = builder.build()
second = builder.build()
# `first` and `second` both resolve Clock, but they cache
# singletons separately - the resolver state is per-container.
assert first.resolve(Clock) is not second.resolve(Clock)

builder.bind(Cache, make_cache)
fresh = builder.build()
# `first` and `second` still know only about Clock; only `fresh`
# knows about Cache.
```

This is the "two builds = two independent containers, equivalent
in bindings" guarantee.

## When NOT to use the builder

The default `Container()` constructor is unfrozen and lets you
`bind` directly. Use it for:

- **tests** that need to add or vary a single binding per case;
- **scripts** with a handful of bindings where a builder would
  be ceremony;
- **adapters** that wire dependencies imperatively from
  framework-specific introspection (Flask blueprints, FastAPI
  dependencies, etc.).

For application-level wiring with modules, configuration
loaders, and a long-lived container, prefer the builder: it
makes the seal explicit, and downstream code that receives a
`Container` knows the wiring is final.
