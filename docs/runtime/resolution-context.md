# Resolution context

The `ResolutionContext` is the per-resolution scratchpad the
runtime maintains for one in-flight `resolve()` (or `aresolve()`)
operation. It carries the stack of tokens the resolver is
currently working on - the data the cycle detector inspects to
spot `A -> B -> A` patterns - and serves as the anchor for scope
state and per-scope teardown registries added in later commits.

```python
from tripack_runtime import (
    ResolutionContext,
    aresolution_scope,
    current_context,
    resolution_scope,
)
```

## What it is, and what it is NOT

- It IS a small mutable object owned by the resolver for the
  duration of a resolve call. External consumers see only the
  tuple snapshot via `stack` and a membership check via `in`.
- It IS NOT a container of bindings. The `DependencyGraph` is.
- It IS NOT thread-shared. It lives behind a `ContextVar`, so
  every sync thread and every `asyncio.Task` gets its own copy
  on entry.

## The data model

```python
class ResolutionContext:
    __slots__ = ("_stack",)

    @property
    def stack(self) -> tuple[DependencyToken, ...]: ...
    def __contains__(self, token: object) -> bool: ...

    @contextmanager
    def resolving(self, token: DependencyToken) -> Iterator[None]: ...

    @asynccontextmanager
    async def aresolving(
        self, token: DependencyToken
    ) -> AsyncIterator[None]: ...
```

The `stack` property returns a fresh tuple each time it is read,
so a caller that captures it gets a frozen snapshot, never a
live view of the underlying list.

## Push/pop with `resolving`

The only correct way to mutate the stack is through the
`resolving` / `aresolving` context managers. They push on entry
and pop on exit, **including when the body raises**, which is
what keeps the stack consistent with the call chain:

```python
ctx = ResolutionContext()
with ctx.resolving(Clock):
    assert Clock in ctx
    assert ctx.stack == (Clock,)
    with ctx.resolving(Cache):
        assert ctx.stack == (Clock, Cache)
    assert ctx.stack == (Clock,)
assert ctx.stack == ()
```

The async counterpart has identical semantics and is meant for
`aresolve()` paths:

```python
async with aresolution_scope() as ctx:
    async with ctx.aresolving(Clock):
        ...
```

## The current context

Most callers do not construct a `ResolutionContext` directly.
They open a `resolution_scope()` (or `aresolution_scope()`) and
let the runtime do it for them. While the scope is open,
`current_context()` returns the active context; outside any
scope it returns `None`.

```python
from tripack_runtime import current_context, resolution_scope

assert current_context() is None

with resolution_scope() as ctx:
    assert current_context() is ctx
    with ctx.resolving(Clock):
        ...

assert current_context() is None
```

The scope managers store the context in a module-level
`ContextVar`, then `reset()` the token on exit. That is the only
way the context becomes visible to the rest of the runtime
without being threaded as an explicit parameter through every
internal call.

## Why `ContextVar`?

`ContextVar` is what makes async resolution sane. When you
launch two coroutines under `asyncio.gather`, each gets its own
copy of the variable. Their pushes do not leak across the
`await` boundary, even when both coroutines are resolving the
same factory concurrently:

```python
async def worker(label: str) -> tuple[object, ...]:
    async with aresolution_scope() as ctx:
        async with ctx.aresolving(label):
            await asyncio.sleep(0)  # yield to the scheduler
            return ctx.stack


stacks = await asyncio.gather(worker("A"), worker("B"))
assert stacks == [("A",), ("B",)]
```

A thread-local would not give us this. A global mutable
container would not either - they would both let coroutine B
observe coroutine A's stack mid-resolve.

## Why no `pop()` / `push()` on the surface?

Manual push/pop is the easiest way to leave the stack in a
broken state: forget the `pop` after a raise, double-pop on a
nested unwind, push to a borrowed context from a different
thread. Restricting mutation to a `with`-style manager means the
unwind path is enforced by Python itself, not by discipline.

## Why `__slots__`?

The context carries one attribute and is created once per
resolve. `__slots__ = ("_stack",)` keeps the per-instance
footprint small and prevents accidental attribute creation - a
typo on a setter, a misnamed assignment in a subclass - that
would silently add state to what is meant to be a small,
opaque, internal object.
