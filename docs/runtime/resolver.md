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

## Lifecycles

```python
class Resolver:
    def teardowns(self) -> tuple[Closeable | AsyncCloseable, ...]: ...
```

The resolver dispatches on `binding.lifecycle` for every call.
Two lifecycles are supported today; `SCOPED` raises
`NotImplementedError` and lands in 3.7.

### Transient

Every call to `resolve` (or `aresolve`) invokes the factory and
returns a fresh result. There is no cache and no teardown
registration.

```python
graph.register(Binding(token=Clock, factory=Clock))

a = resolver.resolve(Clock)
b = resolver.resolve(Clock)
assert a is not b
```

### Singleton

The first call builds the instance and caches it; subsequent
calls return the cached one. The cache check runs **before**
the cycle-detection push, so a hit costs one dict lookup and
does not touch the resolution stack.

```python
graph.register(
    Binding(token=Clock, factory=Clock, lifecycle=Lifecycle.SINGLETON)
)

a = resolver.resolve(Clock)
b = resolver.resolve(Clock)
assert a is b
```

A factory that raises does NOT poison the cache: the next call
retries. A SINGLETON whose factory recursively resolves itself
trips the cycle detector and leaves the cache empty.

#### Async-only SINGLETON, sync read

A SINGLETON registered with `async_factory` (no sync `factory`)
is normally rejected by sync `resolve`. Once `aresolve` has
constructed it, the cache hit on subsequent `resolve` calls
bypasses construction entirely and returns the cached instance.
This is a feature: async-built singletons are still readable
from sync code paths.

```python
async def make_clock() -> Clock:
    return Clock()

graph.register(
    Binding(
        token=Clock,
        async_factory=make_clock,
        lifecycle=Lifecycle.SINGLETON,
    )
)

await resolver.aresolve(Clock)   # constructs and caches
resolver.resolve(Clock)          # cache hit, returns the cached one
```

## Teardown registration

When a SINGLETON is built and its instance exposes a `close`
method (sync) or `aclose` method (async), the resolver appends
it to an internal teardown list:

```python
graph.register(
    Binding(
        token=ConnectionPool,
        factory=ConnectionPool,
        lifecycle=Lifecycle.SINGLETON,
    )
)

pool = resolver.resolve(ConnectionPool)
assert resolver.teardowns() == (pool,)
```

`teardowns()` returns a tuple snapshot in **registration
order**, which is also construction order. The eventual
teardown propagation (3.9) will iterate this list in reverse so
dependents are closed before the services they depend on.

The classifier is structural (duck-typed): any instance with a
callable `close` or `aclose` attribute qualifies. TRANSIENT
instances are NEVER registered, even when they expose
`close` - their lifetime is the caller's responsibility, and
the runtime has no way to know when they go out of use.

This commit only **collects** the targets. The actual `close` /
`aclose` invocation, the LIFO ordering, and the cross-scope
propagation arrive in 3.9.

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
