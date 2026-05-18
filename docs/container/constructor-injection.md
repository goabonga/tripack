# Automatic constructor injection

`Container.bind_class` and the `@inject` decorator let you
register a class (or any callable) without manually wiring its
constructor parameters - the container introspects the
factory's signature at bind-time, validates that every
parameter can be resolved, and at resolve-time pulls each
annotated dependency from the container before invoking the
factory.

```python
from tripack_container import (
    Container,
    ContainerBuilder,
    inject,
)
```

## API

```python
class Container:
    def bind_class[T](
        self,
        cls: type[T],
        *,
        lifecycle: Lifecycle | None = None,
    ) -> None: ...


class ContainerBuilder:
    def bind_class[T](
        self,
        cls: type[T],
        *,
        lifecycle: Lifecycle | None = None,
    ) -> Self: ...


def inject[**P, R](fn: Callable[P, R]) -> Callable[P, R]: ...
```

`bind_class(cls)` is equivalent to `bind(cls, cls,
auto_inject=True)`. The `@inject` decorator is a marker that
makes `bind(token, factory)` behave as if `auto_inject=True`
was passed - the bind picks up the attribute and wraps the
factory.

## Example: bind_class

```python
class Repository: ...


class Service:
    def __init__(self, repo: Repository) -> None:
        self.repo = repo


container = Container()
container.bind_class(Repository)
container.bind_class(Service)
service = container.resolve(Service)
```

The container inspects `Service.__init__`, sees `repo:
Repository`, and resolves `Repository` from the registered
bindings before calling `Service(repo=<the repository>)`.

## Example: @inject on a factory function

```python
@inject
def make_app(clock: Clock, cache: Cache) -> App:
    return App(clock, cache)


container.bind(Clock, make_clock)
container.bind(Cache, make_cache)
container.bind(App, make_app)
app = container.resolve(App)
```

The function remains directly callable outside the container -
`make_app(real_clock, real_cache)` works as a plain function.
The marker only kicks in when the function is passed to `bind`.

## Defaults are respected

Parameters with a default value that point to an **unbound**
type keep their default; bound types still take precedence
over defaults:

```python
class Service:
    def __init__(self, clock: Clock, retries: int = 3) -> None:
        self.clock = clock
        self.retries = retries


container = Container()
container.bind(Clock, make_clock)
container.bind_class(Service)
container.resolve(Service).retries == 3          # int not bound, default kept

container.bind(int, lambda: 42)
container.bind_class(Service)  # would conflict with the previous bind,
# so build a fresh container in practice
```

A parameter without an annotation but with a default is also
skipped. A parameter with neither raises `BindingError`
**at bind time**:

```python
def broken(missing_anno) -> Service:
    return Service(...)


container.bind(Service, broken, auto_inject=True)
# -> BindingError: Cannot auto-inject ...: parameter 'missing_anno' has
#    no annotation and no default.
```

## Async injection

`@inject` on an `async def` factory works the same way; the
container drives it through `aresolve`:

```python
@inject
async def make_app(clock: Clock) -> App:
    return App(clock)


container.bind(Clock, make_clock_async)
container.bind(App, make_app)
app = await container.aresolve(App)
```

The wrapper detects `async def` via
`inspect.iscoroutinefunction` and produces an async wrapper
that `await`s every dependency before `await`ing the factory.

## Lifecycle interaction

`bind_class` accepts the same `lifecycle=` keyword as `bind`,
and the `@inject` marker stacks freely with the
`@singleton` / `@scoped` / `@transient` decorators:

```python
@singleton
@inject
def make_app(clock: Clock, cache: Cache) -> App:
    return App(clock, cache)


container.bind(App, make_app)
container.resolve(App) is container.resolve(App)  # True (SINGLETON)
```

`@inject` and `@singleton` set different attributes
(`__tripack_inject__` and `__tripack_lifecycle__`), so they
do not interfere.

## Bind-time error vs. resolve-time error

The validation distinguishes two error surfaces:

- **bind-time** (`BindingError`): a parameter is structurally
  un-injectable (no annotation, no default). The error fires
  at `Container.bind` / `ContainerBuilder.bind` time, before
  any resolve attempt. The builder validates eagerly so the
  error fires at the chained `.bind` call, not at `.build()`.
- **resolve-time** (`ResolutionError`): a required (no-default)
  annotated dependency is not bound in the container. The
  error fires when the auto-injected factory is invoked.
  Parameters with a default are caught here and silently
  fall back to the default value.

## Builder semantics

`ContainerBuilder.bind_class` and `@inject`-marked factories
combine with the builder normally. The actual factory wrapping
happens at `build()` time, when the new `Container` is
available to close over. Each `build()` therefore produces a
container whose auto-injected factories point at itself - two
successive builds yield two independent containers, and a
`@singleton`-tagged auto-injected service is cached separately
per container.
