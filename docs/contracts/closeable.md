# Closeables

A closeable is anything that holds a resource the framework should
release when the owning container or scope shuts down: a database
connection, an HTTP session, a file handle, a thread pool, an
event-loop subscription. Tripack defines two structural protocols
the runtime probes against any singleton or scoped instance it
caches.

```python
from tripack_contracts import Closeable, AsyncCloseable
```

## `Closeable`

```python
from typing import Protocol


class Closeable(Protocol):
    def close(self) -> None:
        ...
```

A single no-arg method, returning `None`. Compatible by construction
with [`contextlib.closing`](https://docs.python.org/3/library/contextlib.html#contextlib.closing).

### Example

```python
from tripack_contracts import Closeable


class FileHandle:
    def __init__(self, fp: object) -> None:
        self._fp = fp
        self._closed = False

    def close(self) -> None:
        if self._closed:
            return
        # release the underlying resource here
        self._closed = True


handle: Closeable = FileHandle(open_log_file())
handle.close()
handle.close()    # second call is a no-op, see "Idempotency" below
```

## `AsyncCloseable`

```python
class AsyncCloseable(Protocol):
    async def aclose(self) -> None:
        ...
```

Same shape, awaitable. The method is named `aclose` rather than
`close` to match the convention used by
[`contextlib.aclosing`](https://docs.python.org/3/library/contextlib.html#contextlib.aclosing)
and stdlib async generators.

### Example

```python
import asyncio

from tripack_contracts import AsyncCloseable


class AsyncConnectionPool:
    def __init__(self) -> None:
        self._closed = False

    async def aclose(self) -> None:
        if self._closed:
            return
        # drain in-flight checkouts here
        self._closed = True


pool: AsyncCloseable = AsyncConnectionPool()
asyncio.run(pool.aclose())
```

## Idempotency: a hard expectation

Both `close()` and `aclose()` MUST be safe to call multiple times.
The runtime guarantees a single call under normal teardown, but
cannot guarantee single invocation if an exception interrupts the
teardown loop. Implementations therefore short-circuit on a second
call:

```python
def close(self) -> None:
    if self._closed:
        return
    # release ...
    self._closed = True
```

Failing to honour idempotency is a footgun:

- A second `close()` that raises `ValueError("already closed")`
  hides the original exception in the runtime's teardown
  `ExceptionGroup`.
- A second `aclose()` that re-runs the release logic risks
  double-close on the underlying resource (TCP RST, double-free,
  duplicate event-loop callbacks).

## How the runtime uses these protocols

This is a **preview** of behaviour that lands in `tripack-runtime`
and `tripack-container`:

| Lifecycle | Tracked for teardown | Released by |
| --- | --- | --- |
| `TRANSIENT` | no | not tracked - the caller owns the instance |
| `SINGLETON` | yes | the container, on `close()` / `aclose()` |
| `SCOPED` | yes | the scope, on context-manager exit |

The runtime inspects every cached instance, registers it if it
implements `Closeable` or `AsyncCloseable`, and closes them in
reverse creation order (LIFO) at teardown. Individual failures are
collected into an `ExceptionGroup` so one bad cleanup does not mask
the others.

## A class can satisfy both

Nothing prevents a class from implementing `close` AND `aclose`. The
runtime prefers `aclose` when teardown is performed asynchronously
(scope exited via `async with`, container closed via
`await container.aclose()`), and falls back to `close` otherwise.
Implementations that need to work in both modes typically delegate:

```python
class DualConnection:
    def __init__(self) -> None:
        self._closed = False

    def close(self) -> None:
        if self._closed:
            return
        # synchronous teardown ...
        self._closed = True

    async def aclose(self) -> None:
        if self._closed:
            return
        # async teardown, may await ...
        self._closed = True
```
