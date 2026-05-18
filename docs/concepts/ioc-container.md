# IoC container

An **IoC container** is the runtime that turns the
[inversion-of-control principle](inversion-of-control.md) into
a usable mechanism. It owns a registry of bindings and a
resolver that constructs instances on demand. Conceptually:

```
                +------------------+
                |    Container     |
                |                  |
   bindings --> | token -> factory | <-- resolver
                |                  |
                +------------------+
                          |
                          v
                   live instances
```

Three responsibilities, in one object:

1. **Registry**: store which factory produces which token, and
   under what lifecycle (transient / singleton / scoped).
2. **Resolver**: given a token, look up its binding, recurse
   into its dependencies, invoke factories in the right order,
   return the constructed instance.
3. **Lifecycle manager**: cache singletons, scope scoped
   bindings, tear down closeables in LIFO order on exit.

## A minimal example

```python
from tripack_container import Container

container = Container()
container.bind(Clock, SystemClock)
container.bind(Cache, MemoryCache)
container.bind_class(App)

app = container.resolve(App)
```

Five lines: three bindings + one resolution. The container
walks `App.__init__` annotations, sees `Clock` and `Cache`,
resolves them recursively, and calls `App(clock, cache)`. The
consumer's code does not order construction, does not hold
intermediate references, does not pass anything around.

## What's in the registry

Each entry is a `Binding`:

```python
@dataclass(frozen=True, slots=True)
class Binding:
    token: DependencyToken           # who is this for
    factory: Callable[..., Any] | None
    async_factory: Callable[..., Awaitable[Any]] | None
    lifecycle: Lifecycle             # TRANSIENT / SINGLETON / SCOPED
    auto_inject: bool
```

Exactly one of `factory` / `async_factory` is set per binding,
so the container knows whether `resolve` or `aresolve` can
drive it. `auto_inject` flips the resolver into constructor-
introspection mode.

## What the resolver does

A `resolve(token)` call walks the binding's factory signature
once (at bind time, via `inspect.get_annotations`), then at
resolve time:

1. Looks up the binding in the registry.
2. Checks the lifecycle cache (singleton dict on the resolver,
   scoped dict on the active `Scope`) for an existing
   instance.
3. On a cache miss, opens a cycle-detection frame around the
   token (so a factory that recursively resolves the same
   token raises `CircularDependencyError` rather than
   stack-overflowing).
4. Invokes the factory. If `auto_inject` is on, each
   parameter is recursively resolved first.
5. Caches the result if the lifecycle warrants it.
6. Registers `close` / `aclose` on the scope's teardown list
   when the new instance is a closeable.

Async resolution mirrors the same path with `aresolve` /
`ascope`. Concurrent `asyncio.gather` calls open their own
resolution contexts via `ContextVar`, so two parallel
resolutions of the same singleton observe the same
canonical instance (the registration guard is race-safe).

## Lifecycles in a sentence each

- **`TRANSIENT`**: build a fresh instance on every resolve.
  No cache.
- **`SINGLETON`**: build once per container. Cached on the
  resolver. Survives every scope.
- **`SCOPED`**: build once per `Scope`. Cached on the scope.
  Distinct across scopes; requires one to be open.

See [`Lifecycle`](../contracts/lifecycle.md) for the contract
and [`Container.scope`](../container/scopes.md) for the
runtime semantics.

## Composition

Real wiring grows past a handful of binds. The container
exposes three layers of composition:

- **Provider helpers** (`@singleton`, `@scoped`, `@transient`,
  plus async cousins): tag a factory with its lifecycle so
  `bind` picks it up automatically.
- **Modules** (`Module` Protocol + `ContainerBuilder.install`):
  bundle a set of related bindings under one
  `register(builder)` call.
- **Configuration loaders** (`Container.from_toml` /
  `from_json` / `from_yaml`): describe the entire wiring
  declaratively in a text file; the loader resolves dotted
  Python names to live objects.

A typical application combines all three: helpers on
individual factories, modules per feature, a single TOML at
the root for environment-specific overrides.

## Composition root

The point in the program where the container is built and the
top-level service is resolved is called the **composition
root**. It is usually:

- one place per process (the entry point);
- as small as possible (one builder, one `build()`, one
  resolve, one `with container:` for teardown);
- the **only** place that touches `Container` directly. Every
  other module receives its dependencies via constructor
  parameters or `@inject`.

```python
def main() -> None:
    builder = ContainerBuilder()
    builder.install(infrastructure_module)
    builder.install(domain_module)
    builder.bind(Config, lambda: Config.load(os.environ["APP_CONFIG"]))

    with builder.build() as container:
        container.resolve(App).run()
```

Outside `main`, no service should know that a `Container`
exists.

## When a container hurts more than it helps

- **A 30-line script**. Just instantiate the three objects.
- **Hot paths**. The resolver walks a tree on every resolve;
  for tight loops, look up the resolved value once at startup
  and cache it.
- **Tests that need surgical wiring**. The container is
  optimised for the typical case; an unusual test may be
  clearer with manual `App(fake_clock, fake_cache)`.

The container is a force multiplier when the wiring is large
and varied. Below that scale, plain dependency injection (by
hand, in the composition root) is the right answer.
