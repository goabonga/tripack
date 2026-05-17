# Dependency graph

The `DependencyGraph` is the runtime's source of truth for
registered bindings. It is a token-keyed registry of `Binding`
instances with strict semantics around duplicates, conflicts, and
missing lookups.

```python
from tripack_runtime import DependencyGraph
```

## What it is, and what it is NOT

- It IS a flat key-value store. One token, one binding. The order
  of insertion is preserved.
- It IS NOT a caching layer. Resolution, lifecycle handling, scope
  ownership and teardown live in separate components that consult
  the graph via `lookup`.
- It IS NOT thread-safe. Real-world containers are typically built
  on a single thread at startup. A concurrent-write story can be
  layered on top later behind the same surface.

## API

```python
class DependencyGraph:
    def register(self, binding: Binding) -> None: ...
    def lookup(self, token: DependencyToken) -> Binding: ...
    def bindings(self) -> tuple[Binding, ...]: ...
    def __len__(self) -> int: ...
    def __iter__(self) -> Iterator[DependencyToken]: ...
    def __contains__(self, token: object) -> bool: ...
```

## Registration semantics

`register(binding)` behaves differently based on whether the
binding's token is already known:

| Existing entry | Incoming binding | Result |
| --- | --- | --- |
| _none_ | any | stored as-is |
| structurally identical | same fields | **no-op** (idempotent) |
| different on any field | mismatch | `BindingError` |

The idempotency case is what lets a module re-register the same
binding under multiple call paths (a defensive `install_clock()`
called both at startup and inside a `setup()` helper) without
triggering false conflicts.

Conflicts include any field difference: a different `factory`, a
different `lifecycle`, a different `auto_inject`, or a transition
between sync and async factory shapes.

```python
from tripack_runtime import Binding, DependencyGraph

graph = DependencyGraph()
graph.register(Binding(token=Clock, factory=Clock))

# Idempotent: same fields - no error.
graph.register(Binding(token=Clock, factory=Clock))

# Conflict: same token, different lifecycle.
graph.register(
    Binding(token=Clock, factory=Clock, lifecycle=Lifecycle.SINGLETON)
)
# -> BindingError: Conflicting binding for token <class 'Clock'>: ...
```

## Lookup semantics

`lookup(token)` returns the registered binding, or raises
`ResolutionError` if none is registered. The chained `KeyError` is
preserved as `__cause__` for tracebacks.

```python
graph.lookup(Clock)        # -> Binding(...)
graph.lookup(MissingToken) # -> raises ResolutionError
```

## Iteration helpers

```python
len(graph)             # number of registered tokens
list(graph)            # tokens in insertion order
Clock in graph         # presence check
graph.bindings()       # tuple of all bindings, snapshot
```

`bindings()` returns a tuple, not a view, so the caller cannot
mutate the underlying mapping by holding onto the snapshot.

## Tokens of every kind coexist

The graph keys are `DependencyToken`, so a class, a string, and a
hashable tuple can all be registered side-by-side without
collisions:

```python
graph.register(Binding(token=Clock, factory=Clock))
graph.register(Binding(token="primary-clock", factory=Clock))
graph.register(Binding(token=("clock", "secondary"), factory=Clock))

assert len(graph) == 3
```

## Why no `unregister`?

Bindings are intentionally **monotonic** during a container's
lifetime: you can add, you cannot remove. Removing a binding mid-
flight would force the resolver to invalidate caches and scopes
that captured a reference, which makes the concurrency model much
harder to reason about.

If a test needs a clean slate, build a new `DependencyGraph` (and a
new container) rather than mutating an existing one.

## Why `__slots__`?

The graph instance carries one attribute. `__slots__ = ("_bindings",)`
prevents accidental attribute creation (e.g. a typo on a setter
that would silently add a new attribute) and avoids the per-
instance `__dict__` overhead.
