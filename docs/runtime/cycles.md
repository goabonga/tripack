# Circular dependency detection

A circular dependency is the easiest way to make a container
hang. If `Cache` needs `Clock` and `Clock` needs `Cache`, a
naive resolver would recurse forever. The cycle detector turns
that into a single, well-formed error before the recursion ever
starts.

```python
from tripack_runtime import (
    aguarded_resolving,
    check_for_cycle,
    guarded_resolving,
)
```

## The contract

Cycle detection operates on a `ResolutionContext`. When the
resolver opens a frame for a token, the guard checks whether
that token already appears on the active stack:

- if it does NOT, the new token is pushed and resolution
  proceeds normally;
- if it DOES, a `CircularDependencyError` is raised before any
  state change.

The error carries a `cycle` attribute - an ordered tuple of
tokens forming the loop, by convention starting and ending with
the same token (`A -> B -> A`).

## API

```python
def check_for_cycle(
    ctx: ResolutionContext,
    token: DependencyToken,
) -> None: ...

@contextmanager
def guarded_resolving(
    ctx: ResolutionContext,
    token: DependencyToken,
) -> Iterator[None]: ...

@asynccontextmanager
async def aguarded_resolving(
    ctx: ResolutionContext,
    token: DependencyToken,
) -> AsyncIterator[None]: ...
```

`check_for_cycle` is the raw predicate; the two `guarded_*`
context managers combine the check with the matching
`ResolutionContext.resolving` / `aresolving` push.

## Example: a self-loop

```python
ctx = ResolutionContext()
with ctx.resolving(Clock):
    check_for_cycle(ctx, Clock)
    # -> CircularDependencyError: Circular dependency detected: Clock -> Clock
```

A token that re-enters itself yields a length-2 cycle. That is
not a redundancy; the duplicate close on the right makes the
loop unambiguous even when the cycle has a single step.

## Example: a multi-step cycle

```python
ctx = ResolutionContext()
with ctx.resolving(Clock), ctx.resolving(Cache), ctx.resolving(Logger):
    check_for_cycle(ctx, Clock)
    # cycle == (Clock, Cache, Logger, Clock)
```

The reported cycle starts at the *first* occurrence of the
re-entering token. Tokens sitting below that point are part of
the surrounding resolution but not of the loop, and they are
deliberately excluded from the message.

## Example: guarded resolution

`guarded_resolving` is the high-level entry point the resolver
will use. It is a thin combination of the predicate and the
existing context manager:

```python
ctx = ResolutionContext()
with guarded_resolving(ctx, Clock):
    assert ctx.stack == (Clock,)
    with guarded_resolving(ctx, Cache):
        assert ctx.stack == (Clock, Cache)
        # Re-entering Clock now would raise before the push,
        # leaving the stack unchanged on the way out.
```

The async counterpart `aguarded_resolving` has identical
semantics for `aresolve()` paths.

## Why fail before pushing?

The guard intentionally raises *before* the push. If the check
ran after the push, a failed guard would have to roll back the
mutation, and any code that observed the stack mid-guard (a
logger, an inspector, an error handler) would briefly see a
state that contains the loop. Refusing the push keeps the
context's invariant simple: "every token on the stack
corresponds to a live, non-failing resolution frame".

## Why class identity for class tokens?

The detector compares tokens with `==` via membership
(`token in ctx`), which for classes degenerates to identity.
This matches the resolver's binding lookup, where two distinct
classes named `Cache` in two different modules are different
tokens and must not be conflated.

## What the detector does NOT do

- It does **not** keep a global history of past resolutions.
  Each resolution starts with a fresh context; previously seen
  tokens do not interact with the current one.
- It does **not** detect "logical" cycles - two factories that
  call into each other via a third-party object cache, for
  instance, are invisible to the resolver and to the guard.
- It does **not** distinguish cycles introduced by
  configuration from cycles introduced by faulty factories.
  Both surface the same exception; the cause is up to the
  reader of the traceback.
