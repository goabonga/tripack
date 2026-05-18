# Bindings

`Container.bind` registers a factory for a token under a chosen
lifecycle. It is the foundation every other piece of the
container builds on - the builder (4.3) groups bind calls into
a sealed unit, modules (4.4) package them as reusable bundles,
provider helpers (4.5) decorate factories with the right
lifecycle, constructor injection (4.6) inspects the factory
signature, and the config loaders (4.9-4.11) translate
external declarations into bind calls.

```python
from tripack_contracts import Lifecycle
from tripack_container import Container

container = Container()
container.bind(Clock, make_clock)
container.bind(Cache, make_cache, lifecycle=Lifecycle.SINGLETON)
container.bind(Session, make_session, lifecycle=Lifecycle.SCOPED)
```

## API

```python
class Container:
    @overload
    def bind[T](
        self,
        token: type[T],
        factory: Callable[..., T],
        *,
        lifecycle: Lifecycle = Lifecycle.TRANSIENT,
        auto_inject: bool = False,
    ) -> None: ...

    @overload
    def bind[T](
        self,
        token: type[T],
        factory: Callable[..., Awaitable[T]],
        *,
        lifecycle: Lifecycle = Lifecycle.TRANSIENT,
        auto_inject: bool = False,
    ) -> None: ...
```

Two overloads keep typing precise: a sync factory yields a
container that returns instances directly via `resolve`; an
async factory yields one that returns instances via
`await aresolve`.

## Sync vs async detection

`bind` auto-detects whether ``factory`` is a regular function
or an `async def` via `inspect.iscoroutinefunction` and routes
it to the matching `Binding` slot under the hood. No keyword
toggle is needed:

```python
def make_clock() -> Clock:
    return Clock()

async def make_clock_async() -> Clock:
    return Clock()

container.bind(Clock, make_clock)         # sync slot
container.bind(Clock, make_clock_async)   # async slot (different binding)
```

A sync factory bound under a token is rejected by `aresolve`?
No - the runtime resolver handles a sync factory through both
paths: `resolve` calls it directly, `aresolve` calls it
directly too (no await needed). Conversely an async-only
factory raises `ResolutionError` when `resolve` is used, with
a message pointing at `aresolve`.

## Idempotent re-bind

Re-binding the same `(token, factory, lifecycle, auto_inject)`
tuple is a no-op (delegated to the graph's idempotent
register). Any difference on those fields raises
`BindingError` at bind time, not at resolve time, so a
configuration mistake fails fast:

```python
container.bind(Clock, make_clock)               # OK
container.bind(Clock, make_clock)               # OK, no-op
container.bind(Clock, other_make_clock)         # BindingError: conflicting
container.bind(Clock, make_clock,
               lifecycle=Lifecycle.SINGLETON)   # BindingError: conflicting
```

## Lifecycles

`bind` accepts any `Lifecycle` value; the actual caching
semantics live in the runtime (`docs/runtime/resolver.md`,
`docs/runtime/scopes.md`):

- `TRANSIENT` (default) - fresh instance per resolve;
- `SINGLETON` - cached on the container's resolver, shared
  across all scopes;
- `SCOPED` - cached on the active `Scope`, distinct across
  scopes, requires an open scope when resolved.

## Typed returns

The PEP 695 generic on `bind` and `resolve` preserves the
type of the bound token end to end. mypy strict sees:

```python
container.bind(Clock, make_clock)
clock = container.resolve(Clock)
assert_type(clock, Clock)         # static check, no runtime cost
```

A future refactor that loses the generic parameter would fail
mypy on the `assert_type` line before the consumer notices.

## What `auto_inject` does (and does NOT do yet)

The keyword is accepted today and stored on the underlying
binding, but the actual constructor-injection wiring is added
in 4.6. Until then a binding with `auto_inject=True` behaves
like a normal one - the factory is called with the arguments
the framework would pass (none for now, since the runtime's
resolver invokes factories with no args).
