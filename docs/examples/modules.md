# Modules

A `Module` is a reusable bundle of bindings. Instead of
repeating the same `bind` calls in every composition root,
package them into a class with a `register(builder)` method
and `install` the module wherever it is needed.

## A first module

```python
from tripack_contracts import Lifecycle
from tripack_container import ContainerBuilder, Module


class Clock:
    def now(self) -> float:
        return 1234567890.0


class Cache:
    def __init__(self) -> None:
        self._store: dict[str, str] = {}


class InfrastructureModule:
    def register(self, builder: ContainerBuilder) -> None:
        builder.bind(Clock, Clock, lifecycle=Lifecycle.SINGLETON)
        builder.bind(Cache, Cache, lifecycle=Lifecycle.SINGLETON)


container = (
    ContainerBuilder()
    .install(InfrastructureModule())
    .build()
)
clock = container.resolve(Clock)
cache = container.resolve(Cache)
```

The `Module` Protocol has one shape: `register(builder)
-> None`. Any class that exposes that method is a module -
no inheritance, no base class, structural typing.

## Composition

Modules can install other modules. The diamond install
problem (two top-level modules each pulling in a common
dependency) is handled by a per-instance guard:

```python
class CacheModule:
    def register(self, builder: ContainerBuilder) -> None:
        builder.bind(Cache, Cache)


class LoggerModule:
    def register(self, builder: ContainerBuilder) -> None:
        builder.bind(Logger, Logger)


class AppModule:
    def __init__(self) -> None:
        # Cached shared instances so the diamond install
        # below collapses to a single install.
        self.cache_module = CacheModule()
        self.logger_module = LoggerModule()

    def register(self, builder: ContainerBuilder) -> None:
        builder.install(self.cache_module)
        builder.install(self.logger_module)


class WebModule:
    def __init__(self, infra: AppModule) -> None:
        self.infra = infra

    def register(self, builder: ContainerBuilder) -> None:
        builder.install(self.infra)             # pulls Cache + Logger
        builder.bind(HttpServer, HttpServer)


class CliModule:
    def __init__(self, infra: AppModule) -> None:
        self.infra = infra

    def register(self, builder: ContainerBuilder) -> None:
        builder.install(self.infra)             # also pulls Cache + Logger
        builder.bind(CliRunner, CliRunner)


# Both Web and CLI pull AppModule. Installing both at the
# top should NOT re-run AppModule's register.
infra = AppModule()
web = WebModule(infra)
cli = CliModule(infra)

container = (
    ContainerBuilder()
    .install(web)
    .install(cli)
    .build()
)
# `infra.register` ran exactly once; `cache_module.register`
# and `logger_module.register` each ran exactly once too.
```

`install` tracks each module **by identity**. A second
`install(same_instance)` is a no-op. Two distinct instances
of the same class are treated as separate modules and both
run - the underlying graph's idempotent register then
deduplicates the actual bindings if they happen to match.

## Order matters for overrides

When two bindings target the same token, the **last one
installed** is the one that takes effect:

```python
class DefaultClockModule:
    def register(self, builder: ContainerBuilder) -> None:
        builder.bind(Clock, Clock)


class TestClockModule:
    def register(self, builder: ContainerBuilder) -> None:
        builder.bind(Clock, FakeClock)


# This raises BindingError: the second bind conflicts.
container = (
    ContainerBuilder()
    .install(DefaultClockModule())
    .install(TestClockModule())
    .build()
)
```

`install` does **not** silently overwrite. To pick a
different binding, omit the conflicting module - do not try
to layer two modules that bind the same token to different
factories.

For test scenarios that need to override a single binding,
the recommended pattern is to install all the production
modules *except* the one that owns the token to be
overridden, then bind the override directly:

```python
container = (
    ContainerBuilder()
    .install(WebModule(infra=AppModule()))   # no DefaultClockModule inside
    .bind(Clock, FakeClock)                  # explicit test override
    .build()
)
```

## When to extract a module

- **Reusable feature**. A "cache + clock + config" trio that
  five applications share belongs in a module so the five
  consumers don't repeat the binds.
- **Plug-in shape**. A third-party library that wants to
  integrate with a Tripack-based application exposes a
  `Module` so the consumer's composition root is one
  `install(...)` line.
- **Test scoping**. A `FakesModule` and a `RealModule` swap
  in test vs production builds.

When the bindings are not shared, a module is overhead. A
single one-off composition root reads better with direct
`builder.bind(...)` chains.

## Where to go next

- [Idempotent registration](idempotent-registration.md): the
  underlying guarantee that makes `install` safe to call
  twice.
- Reference: [`Module`](../container/modules.md),
  [`ContainerBuilder.install`](../container/builder.md).
