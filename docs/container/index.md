# Container

The `Container` is the front door of `tripack-container`. It is
the high-level IoC entry point users program against; the
runtime layer (`Resolver`, `Scope`, ...) stays an implementation
detail visible only when extending the framework.

```python
from tripack_container import Container
```

## What this commit ships

The 4.1 skeleton: a container with sync and async `resolve`
entry points and an empty `DependencyGraph` under the hood. No
binding API yet (lands in 4.2), no scopes wired through (4.7),
no teardown (4.8) - this is the smallest object that can return
"no, that token is not registered" with the right exception.

```python
from tripack_contracts import ResolutionError
from tripack_container import Container

container = Container()

try:
    container.resolve(Clock)
except ResolutionError as exc:
    print(f"unknown token: {exc}")
```

## API

```python
class Container:
    def __init__(self) -> None: ...
    def resolve[T](self, token: type[T]) -> T: ...
    async def aresolve[T](self, token: type[T]) -> T: ...
```

Both methods delegate to the underlying runtime `Resolver`, so
the full contract from
[`docs/runtime/resolver.md`](../runtime/resolver.md) applies:
lifecycle dispatch (TRANSIENT / SINGLETON / SCOPED), cycle
detection across factory recursion, async-only bindings
rejected on the sync path.
