# Idempotent registration

The container distinguishes three outcomes when the same
token is bound more than once: **no-op**, **canonical
return**, and **error**. This page shows when each one
fires and why the contract is what it is.

## Identical re-bind is a no-op

```python
from tripack_container import Container

container = Container()
container.bind(Clock, Clock)
container.bind(Clock, Clock)   # no error, no second binding
```

The graph treats two `Binding` objects as identical when
their `(token, factory, lifecycle, auto_inject)` fields
match. A re-bind with the same tuple does not raise and
does not duplicate the entry. This is what makes
[modules](modules.md) safe to install through more than one
path: the diamond install pattern collapses naturally.

## Different factory raises BindingError

```python
def alt_clock_factory() -> Clock:
    return Clock()


container = Container()
container.bind(Clock, Clock)
container.bind(Clock, alt_clock_factory)
# -> BindingError: Conflicting binding for token <class 'Clock'>: ...
```

A different factory for the same token is a configuration
mistake that the container catches **at bind time**, not at
resolve time. The error names the token so the call site is
obvious from the traceback.

## Different lifecycle also raises

```python
from tripack_contracts import Lifecycle

container = Container()
container.bind(Clock, Clock, lifecycle=Lifecycle.SINGLETON)
container.bind(Clock, Clock, lifecycle=Lifecycle.TRANSIENT)
# -> BindingError: Conflicting binding for token <class 'Clock'>: ...
```

The container does not silently downgrade or upgrade a
binding's lifecycle. A token's lifecycle is part of its
identity in the registry.

## Async-construction race returns the canonical instance

Idempotent registration also protects against the
**concurrent-resolve race**. Two coroutines that
simultaneously resolve the same `SINGLETON` token can both
pass the cache-miss check, both invoke their factory, both
finish building - but only one wins the cache. The other
receives the canonical instance back:

```python
import asyncio

from tripack_contracts import Lifecycle
from tripack_container import ContainerBuilder


can_finish = asyncio.Event()


async def slow_factory() -> Pool:
    await can_finish.wait()
    return Pool()


async def main() -> None:
    container = (
        ContainerBuilder()
        .bind(Pool, slow_factory, lifecycle=Lifecycle.SINGLETON)
        .build()
    )
    task_a = asyncio.create_task(container.aresolve(Pool))
    task_b = asyncio.create_task(container.aresolve(Pool))
    # Both tasks reach the factory's await point...
    for _ in range(5):
        await asyncio.sleep(0)
    can_finish.set()
    a, b = await asyncio.gather(task_a, task_b)
    assert a is b   # the idempotent guard returns the canonical instance


asyncio.run(main())
```

Both factory invocations complete, but only the first writer
populates the cache. The container's teardown registry
records the winner only - the discarded instance is
considered orphaned and is **not** auto-closed (close it
manually if it holds external resources, or rely on Python's
garbage collector if it does not).

The same guard applies to `SCOPED` bindings under concurrent
`aresolve` calls within the same scope.

## Sealed containers refuse all rebinds

A container produced by `ContainerBuilder.build()` is
sealed: any subsequent `Container.bind` call raises
`BindingError`, identical re-binds included.

```python
container = ContainerBuilder().bind(Clock, Clock).build()
container.bind(Clock, Clock)
# -> BindingError: Container is sealed; bindings can no longer
#    be added after ContainerBuilder.build().
```

The seal makes the wiring **immutable** in the application's
hands. To add bindings, build a new container from a new
builder.

## When the guarantee matters

- **Modules with overlapping dependencies**. Two top-level
  modules both pulling in a shared `CacheModule` - the
  per-instance install guard plus the idempotent rebind make
  this safe.
- **Configuration loaders**. A TOML file that lists the same
  token twice (perhaps via an override mechanism layered on
  top) does not produce a duplicate; conflicts are caught at
  load time.
- **Concurrent async resolves**. Two HTTP handlers that
  resolve the same SINGLETON simultaneously cannot create
  two pools by accident.

## When it does NOT save you

- **Two different factories for the same token**. The
  container *will* tell you, but it cannot decide which one
  you meant.
- **An expensive factory that runs on the discarded racer**.
  The work is done; the result is just not cached. Avoid
  side-effects in factories that you do not want to repeat
  if the concurrent race happens.
- **Override semantics in modules**. The container does not
  allow a later module to silently replace an earlier
  binding. Use explicit `bind` after the modules to override.

## Where to go next

- [Modules](modules.md): the install-by-identity pattern
  that relies on idempotent rebinding.
- Reference:
  [`BindingError`](../contracts/errors.md),
  [Container.bind](../container/bindings.md),
  [Container builder](../container/builder.md).
