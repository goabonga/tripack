# Lifetime scopes

A `Scope` is the runtime concept behind the `SCOPED` lifecycle.
It is a bounded cache plus teardown registry: while the scope
is open, every `SCOPED` binding resolves to the same instance;
on exit, every cached instance that exposes `close` or
`aclose` is collected for the eventual teardown propagation
(3.9). The canonical use case is request-scoped dependency
injection in a web framework - one scope per request, the
resolver hands out the same `Request`, `Logger`, `DBConnection`
throughout, and the container closes them on response.

```python
from tripack_runtime import (
    Scope,
    alifetime_scope,
    current_scope,
    lifetime_scope,
)
```

## API

```python
class Scope:
    def lookup(self, token: DependencyToken) -> Any: ...
    def remember(self, token: DependencyToken, instance: Any) -> None: ...
    def teardowns(self) -> tuple[Closeable | AsyncCloseable, ...]: ...

def current_scope() -> Scope | None: ...

@contextmanager
def lifetime_scope() -> Iterator[Scope]: ...

@asynccontextmanager
async def alifetime_scope() -> AsyncIterator[Scope]: ...
```

`Scope` is constructed exclusively by the scope context
managers; users do not instantiate it directly outside tests.
`current_scope()` reads the active scope (or `None`) from the
backing `ContextVar`, which is what the resolver consults to
decide whether a `SCOPED` binding has a home.

## Opening a scope

```python
from tripack_runtime import lifetime_scope, Resolver

resolver = Resolver(graph)
with lifetime_scope() as scope:
    handler = resolver.resolve(RequestHandler)
    # any `SCOPED` resolution inside this block shares `scope`'s cache
```

Inside the block, `current_scope() is scope`. On exit, the
previous value (typically `None`) is restored. The `scope`
object survives the block - callers can still inspect
`scope.teardowns()` after the `with` exits to know what was
cached. The teardown propagation lands in 3.9; for now the
scope only collects targets.

The async variant `alifetime_scope` has identical semantics:

```python
async with alifetime_scope() as scope:
    handler = await resolver.aresolve(RequestHandler)
```

Each `asyncio.Task` opened inside the surrounding context
inherits its own copy of the backing `ContextVar`, so two
coroutines launched under `asyncio.gather` each open and close
their own scope without interfering. Nested scopes work the
same way: the inner scope shadows the outer for the duration of
its block, and the outer is restored on exit.

## SCOPED lifecycle dispatch

When the resolver encounters a `SCOPED` binding, it:

1. reads `current_scope()`;
2. if no scope is active, raises `ScopeError` immediately
   (the cycle-detection stack is not pushed - the error names
   the missing scope, not a phantom resolution frame);
3. otherwise consults `scope.lookup(token)` for a cached
   instance, returns it on a hit;
4. on a miss, opens a cycle-detection frame, invokes the
   factory, then `scope.remember(token, instance)`.

```python
graph.register(
    Binding(token=Clock, factory=Clock, lifecycle=Lifecycle.SCOPED)
)

# No active scope: ScopeError
resolver.resolve(Clock)
# -> ScopeError: Token <class 'Clock'> has SCOPED lifecycle but no
#    scope is active; open one with lifetime_scope() or alifetime_scope()
#    before resolving.

# Inside a scope: cached for the scope duration
with lifetime_scope():
    a = resolver.resolve(Clock)
    b = resolver.resolve(Clock)
    assert a is b

# Across scopes: separate instances
with lifetime_scope():
    c = resolver.resolve(Clock)
with lifetime_scope():
    d = resolver.resolve(Clock)
assert c is not d
```

## Teardown registry

`SCOPED` instances exposing `close` or `aclose` are appended to
`scope.teardowns()` in construction order. `TRANSIENT`
instances are never registered (they have no owner to close
them); `SINGLETON` instances are registered on the resolver
instead, not on any scope:

```python
with lifetime_scope() as scope:
    pool = resolver.resolve(ConnectionPool)  # SCOPED + closeable
    assert scope.teardowns() == (pool,)
```

The classifier is structural duck-typing (any object with a
callable `close` or `aclose` qualifies), matching the spirit
of the `Closeable` / `AsyncCloseable` Protocols which are
intentionally not `@runtime_checkable`.

## Factory error semantics

A `SCOPED` factory that raises does NOT poison the cache: the
next call within the same scope retries. A factory that
recursively resolves its own token trips the cycle detector and
leaves the scope's cache empty.

## Boundary with other lifecycles

| Lifecycle | Cache lives on | Survives scope exit |
| --- | --- | --- |
| `TRANSIENT` | nowhere (no cache) | n/a |
| `SCOPED` | the active `Scope` | no - new scope, new instance |
| `SINGLETON` | the `Resolver` | yes - shared across all scopes |

A `SINGLETON` resolved inside a `lifetime_scope()` block is
still the same instance everywhere; the open scope simply does
not see it. A `TRANSIENT` resolution inside a scope is still a
fresh instance every call, and the scope's teardown list stays
empty regardless.
