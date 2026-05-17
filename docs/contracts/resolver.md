# Resolvers

A resolver is the public lookup surface for the container. Consumers
program against a `Resolver` (or `AsyncResolver`) interface rather
than a concrete `Container` class, which keeps consumer code
decoupled from the framework's implementation details and lets tests
swap the resolver for a stub without touching the application.

```python
from tripack_contracts import Resolver, AsyncResolver
```

## `Resolver`

```python
from typing import Protocol


class Resolver(Protocol):
    def resolve[T](self, token: type[T]) -> T:
        ...
```

### Why a method-level TypeVar

The TypeVar `T` is declared **on the method**, not the class. This
matters: a resolver is not parametrised once and for all - the same
resolver handles every token in the container and returns a
correspondingly different type each time. mypy infers the right
return type at each call site:

```python
clock: Clock = resolver.resolve(Clock)        # T = Clock
cache: Cache = resolver.resolve(Cache)        # T = Cache
```

### Example

```python
from tripack_contracts import Resolver


class Clock:
    def __init__(self) -> None:
        self.time = "12:00:00"


class ConstantResolver:
    def resolve[T](self, token: type[T]) -> T:
        return token()


resolver: Resolver = ConstantResolver()
clock = resolver.resolve(Clock)
assert isinstance(clock, Clock)
```

## `AsyncResolver`

```python
class AsyncResolver(Protocol):
    async def resolve[T](self, token: type[T]) -> T:
        ...
```

Same contract, awaitable. Use when the lookup itself may need to
await I/O (e.g., a resolver that lazily provisions a database
connection on first lookup).

### Example

```python
import asyncio

from tripack_contracts import AsyncResolver


class Logger:
    def __init__(self) -> None:
        self.records: list[str] = []


class AsyncConstantResolver:
    async def resolve[T](self, token: type[T]) -> T:
        return token()


resolver: AsyncResolver = AsyncConstantResolver()
logger = asyncio.run(resolver.resolve(Logger))
assert logger.records == []
```

## Resolving by string or hashable token

The Protocol's typed signature accepts only `type[T]` tokens, because
that is the only shape under which mypy can infer the return type.
String and tuple tokens are accepted by the runtime registry but
return `Any` to the caller - their type is, by construction, opaque
to static analysis.

For consumers who reach for string tokens, the recommended pattern
is to wrap the call into a typed helper at the call site:

```python
def resolve_primary_clock(resolver: Resolver) -> Clock:
    return cast(Clock, resolver.resolve("primary-clock"))
```

This keeps the Protocol surface small and pushes the `cast` where the
maintainer knows the intent. A typed wrapper is preferable to widening
the Protocol because it documents the runtime invariant
("primary-clock is always a `Clock`") at the call site.

## Why a Protocol, not a base class

- Consumers do not depend on `tripack_contracts.Resolver` at runtime
  - they import it only for type annotations, and structural typing
  means user-defined resolvers do not need to inherit from anything.
- Test doubles are trivial: a one-method dataclass or a `Mock` with
  `resolve.return_value = ...` satisfies the contract.
- The framework decouples lookup from registration: `Container`
  implements `Resolver` *and* a `bind`-style API, but consumers only
  see the resolver surface.
