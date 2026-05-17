# Resolver

The `Resolver` is the smallest unit that answers the question
"what instance does this token map to?". It composes the three
pieces introduced earlier: the `DependencyGraph` registry, the
`ResolutionContext` stack, and the cycle detector.

```python
from tripack_runtime import Binding, DependencyGraph, Resolver
```

## API

```python
class Resolver:
    def __init__(self, graph: DependencyGraph) -> None: ...
    def resolve[T](self, token: type[T]) -> T: ...
    async def aresolve[T](self, token: type[T]) -> T: ...
```

## Transient lifecycle

This commit ships the **transient** lifecycle: every call to
`resolve` (or `aresolve`) invokes the factory and returns the
result. There is no cache.

```python
graph = DependencyGraph()
graph.register(Binding(token=Clock, factory=Clock))

resolver = Resolver(graph)
a = resolver.resolve(Clock)
b = resolver.resolve(Clock)
assert a is not b
```

Singleton caching, scoped lifetimes, and teardown propagation
arrive in 3.6, 3.7 and 3.9 respectively. Each plugs into the
same dispatch entry point without changing the public surface.

## Sync vs async paths

```python
# sync factory, sync resolve
graph.register(Binding(token=Clock, factory=Clock))
resolver.resolve(Clock)             # returns a Clock

# sync factory, async resolve
await resolver.aresolve(Clock)      # also returns a Clock

# async factory, async resolve
async def make_clock() -> Clock:
    return Clock()

graph.register(Binding(token=Clock, async_factory=make_clock))
await resolver.aresolve(Clock)      # awaited transparently

# async factory, sync resolve -> ResolutionError
resolver.resolve(Clock)
# -> ResolutionError: Binding for token <class 'Clock'> is async-only;
#    use aresolve() to drive it.
```

`aresolve` accepts both factory shapes; `resolve` accepts only
the sync one. This asymmetry is intentional: a sync caller
cannot meaningfully await, so silently calling
`asyncio.run` inside would be the wrong default. The user has
to opt into async by reaching for `aresolve`.

## Cycle detection across factory recursion

A factory that calls back into the resolver participates in the
same cycle-detection stack as its caller. The check fires
before the cycle ever recurses:

```python
def make_clock():
    return resolver.resolve(Cache)

def make_cache():
    return resolver.resolve(Clock)

graph.register(Binding(token=Clock, factory=make_clock))
graph.register(Binding(token=Cache, factory=make_cache))

resolver.resolve(Clock)
# -> CircularDependencyError: Circular dependency detected: Clock -> Cache -> Clock
```

The same guarantee holds on the async path through `aresolve`
and `async_factory`. Each `asyncio.Task` started inside the
scope inherits its own copy of the `ResolutionContext` via the
backing `ContextVar`, so concurrent
`asyncio.gather(resolver.aresolve(...), resolver.aresolve(...))`
calls have independent stacks and do not see each other's
in-flight tokens.

## Scope inheritance

`resolve` and `aresolve` look at `current_context()` first:

- if a scope is already open (because the caller wrapped a
  block in `resolution_scope()` or because a factory is
  recursing into the resolver), the existing context is
  reused;
- if no scope is open, the resolver opens one for the duration
  of the call and tears it down on exit.

This is how a factory's recursive `resolve(...)` call shares
the in-flight stack with its parent call without the caller
needing to thread the context anywhere.

```python
with resolution_scope() as ctx:
    resolver.resolve(Clock)
    # The factory ran inside `ctx`; cycle detection saw the parent's stack.
```

## Lookup-then-guard ordering

`resolve` looks up the binding **before** opening the cycle-
detection frame. A missing token therefore raises
`ResolutionError` without ever pushing the token onto the
stack, keeping the context invariant intact ("every token on
the stack corresponds to a live, non-failing resolution
frame").

## What this commit deliberately does NOT do

- **No constructor injection.** Factories are called with no
  arguments. The container layer in Phase 3 inspects factory
  signatures and resolves each parameter; the runtime stays
  agnostic.
- **No caching.** Only the transient lifecycle is wired up
  here. Singleton/scoped land in 3.6 and 3.7.
- **No teardown.** Even when a factory produces a `Closeable`,
  this commit does not register it for cleanup. Teardown
  propagation lands in 3.9.
- **No thread-safety guarantee.** A single `Resolver` instance
  is safe to call from a single thread or from `asyncio.Task`
  siblings (thanks to `ContextVar`), but two OS threads
  sharing a resolver and mutating its graph race.
