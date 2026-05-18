# Provider helpers

The decorators `singleton`, `scoped`, `transient` (and the
async cousins `async_singleton`, `async_scoped`,
`async_transient`) tag a factory function with a lifecycle.
When the tagged function is later passed to
`Container.bind` or `ContainerBuilder.bind` without an
explicit `lifecycle=` keyword, the binding picks up the
marker; passing `lifecycle=` explicitly always wins.

```python
from tripack_container import (
    ContainerBuilder,
    async_scoped,
    async_singleton,
    async_transient,
    scoped,
    singleton,
    transient,
)
```

## API

```python
def transient[**P, R](fn: Callable[P, R]) -> Callable[P, R]: ...
def singleton[**P, R](fn: Callable[P, R]) -> Callable[P, R]: ...
def scoped[**P, R](fn: Callable[P, R]) -> Callable[P, R]: ...

def async_transient[**P, R](
    fn: Callable[P, Awaitable[R]],
) -> Callable[P, Awaitable[R]]: ...
def async_singleton[**P, R](
    fn: Callable[P, Awaitable[R]],
) -> Callable[P, Awaitable[R]]: ...
def async_scoped[**P, R](
    fn: Callable[P, Awaitable[R]],
) -> Callable[P, Awaitable[R]]: ...
```

Each helper:

- attaches a `__tripack_lifecycle__` attribute to the input
  function via `setattr`,
- returns the input function unchanged (no wrapping), so the
  decorated callable stays usable as a plain factory or even
  as a regular function outside the container,
- preserves the parameter signature `[P, R]` exactly, so mypy
  strict catches signature mismatches at the call site.

## Tagging

```python
@singleton
def make_clock() -> Clock:
    return Clock()


@async_scoped
async def make_session() -> Session:
    return Session()


# The decorator does not change the function shape:
make_clock()                 # still a regular sync call
await make_session()         # still a regular async call
```

## bind integration

`Container.bind` and `ContainerBuilder.bind` look at
`__tripack_lifecycle__` when `lifecycle=` is left at its
`None` default:

```python
@singleton
def make_clock() -> Clock:
    return Clock()


builder.bind(Clock, make_clock)
# binding lifecycle = SINGLETON (picked up from the marker)
```

Explicit `lifecycle=` always wins, so the same factory can be
re-bound under a different lifecycle elsewhere:

```python
@singleton
def make_clock() -> Clock:
    return Clock()


builder.bind(Clock, make_clock, lifecycle=Lifecycle.TRANSIENT)
# binding lifecycle = TRANSIENT (explicit override)
```

An untagged factory with no `lifecycle=` keyword defaults to
`TRANSIENT`, the same default as before.

## Why sync and async helpers?

The async variants exist mainly for precise typing. They
constrain the input to `Callable[P, Awaitable[R]]`, so mypy
strict catches `@async_singleton` applied to a regular `def`
function before runtime:

```python
@async_singleton          # type: error in strict mode
def make_clock() -> Clock:  # not async
    return Clock()
```

At runtime the sync and async helpers do exactly the same
thing - they both call the shared `_tag` helper which sets the
attribute. The distinction is purely about authoring contract.

## Why no `@provider` shorthand?

The plan once mentioned a `provider` / `async_provider` pair
as no-op lifecycle markers. They were dropped: `@transient`
already covers the "this is a factory, default lifecycle"
case, and `@provider` would be a confusing alias. If a future
release needs a name-only marker (for documentation or for a
linter to find), it can be added under a different name
without breaking the existing helpers.
