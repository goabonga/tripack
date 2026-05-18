# Modules

A `Module` is a reusable bundle of bindings - the unit of
composition above raw `bind` calls. A feature, a subsystem or
an infrastructure adapter packages its wiring as a class
exposing a single `register(builder)` method, and consumers
pick it up with one `install` call.

```python
from tripack_container import ContainerBuilder, Module
```

## API

```python
class Module(Protocol):
    def register(self, builder: ContainerBuilder) -> None: ...
```

The protocol is structural: any class with the right method
shape qualifies, no inheritance required. A module typically
holds no state and just dispatches `bind` calls; nothing
prevents a stateful module if the use case calls for it.

```python
class CacheModule:
    def register(self, builder: ContainerBuilder) -> None:
        builder.bind(Cache, make_cache, lifecycle=Lifecycle.SINGLETON)
        builder.bind(CacheConfig, make_cache_config)
```

## Installing

`builder.install(module)` applies the module and returns the
builder for chaining:

```python
container = (
    ContainerBuilder()
    .install(CacheModule())
    .install(LoggingModule())
    .bind(App, make_app)
    .build()
)
```

`install` and `bind` interleave naturally; the order matters
only when one module redefines a token a previous one already
declared, in which case the conflict is detected at
install-time (not at resolve time).

## Composition

A module can install other modules to express layered
dependencies. The classic "feature package" pattern:

```python
class AppModule:
    def register(self, builder: ContainerBuilder) -> None:
        builder.install(CacheModule())   # depends on
        builder.install(LoggingModule()) # depends on
        builder.bind(App, make_app)
```

This is the idiomatic way to express that `App` needs `Cache`
and `Logger` to be wired before it itself is wired.

## Idempotence guard

`install` tracks installed modules by `id()`, so a second
`install(same_instance)` is a no-op:

```python
shared = CacheModule()
builder.install(shared).install(shared)
# `shared.register` ran once; the second install bailed at the guard
```

This is the protection against the "diamond install" pitfall:
two top-level modules each pulling in a common dependency
module should not double-register. As long as the common
dependency is exposed as a shared instance (or installed only
through the top of the diamond), the guard takes care of it.

Two **distinct instances** of the same module class are
treated as separate modules and both run. If their bindings
happen to be structurally identical, the underlying graph's
idempotent `register` deduplicates them; if they conflict,
the second install raises `BindingError`.

## Conflict detection

Two modules cannot bind the same token to different factories:
the second install raises `BindingError` at install-time,
mirroring the conflict semantics of direct `bind` calls. This
fails fast - a misconfiguration is surfaced at builder time,
before any resolution starts.

```python
builder.install(ClockModule())          # binds Clock
builder.install(MockClockModule())
# -> BindingError: Conflicting binding for token <class 'Clock'>: ...
```

If a real use case needs to override a module's binding, the
recommended pattern is to NOT install the original module and
instead rebind the token directly after install. The container
takes the last winner - or, more precisely, the only binding
present in the sealed graph.
