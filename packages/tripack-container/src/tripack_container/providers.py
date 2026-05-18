# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Provider declaration helpers - decorators that tag factories with a lifecycle.

The decorators :func:`singleton`, :func:`scoped` and
:func:`transient` (and their async cousins
:func:`async_singleton`, :func:`async_scoped`,
:func:`async_transient`) mark a factory function with a
``__tripack_lifecycle__`` attribute. When the marked function
is later passed to :meth:`Container.bind` or
:meth:`ContainerBuilder.bind` without an explicit
``lifecycle=`` keyword, the binding picks up the marker;
passing ``lifecycle=`` explicitly always wins.

```python
@singleton
def make_clock() -> Clock:
    return Clock()


@async_scoped
async def make_session() -> Session:
    return Session()


builder.bind(Clock, make_clock)         # picks up SINGLETON
builder.bind(Session, make_session)     # picks up SCOPED
builder.bind(Cache, make_cache,
             lifecycle=Lifecycle.SINGLETON)  # explicit override
```

The helpers return the input function unchanged (no wrapping),
so the decorated callable remains usable as a plain factory or
even as a regular function outside the container. The async
variants exist mainly for precise typing - they constrain the
input to ``Callable[P, Awaitable[R]]`` so mypy strict catches
a misapplication early. At runtime the sync and async helpers
do the same thing.
"""

from collections.abc import Callable, Coroutine
from typing import Any, Final

from tripack_contracts import Lifecycle

LIFECYCLE_ATTR: Final[str] = "__tripack_lifecycle__"


def _tag[**P, R](fn: Callable[P, R], lifecycle: Lifecycle) -> Callable[P, R]:
    """Attach the lifecycle marker without altering the callable.

    Used by all six public helpers below. Variable-name
    ``setattr`` keeps both ruff B010 (constant attribute) and
    mypy quiet on the runtime tag-setting site.
    """
    setattr(fn, LIFECYCLE_ATTR, lifecycle)
    return fn


def transient[**P, R](fn: Callable[P, R]) -> Callable[P, R]:
    """Tag ``fn`` as a ``TRANSIENT`` factory.

    Equivalent to omitting the decorator when binding (the
    binding default is ``TRANSIENT``); the explicit tag is
    useful when the call site cares about communicating intent
    or when a downstream tool reads ``__tripack_lifecycle__``.
    """
    return _tag(fn, Lifecycle.TRANSIENT)


def singleton[**P, R](fn: Callable[P, R]) -> Callable[P, R]:
    """Tag ``fn`` as a ``SINGLETON`` factory."""
    return _tag(fn, Lifecycle.SINGLETON)


def scoped[**P, R](fn: Callable[P, R]) -> Callable[P, R]:
    """Tag ``fn`` as a ``SCOPED`` factory."""
    return _tag(fn, Lifecycle.SCOPED)


# Async helpers are typed against ``Coroutine`` rather than the
# broader ``Awaitable`` so that ``asyncio.run(tagged_fn())``
# type-checks cleanly: asyncio.run only accepts a Coroutine, and
# narrowing here costs nothing for the common ``async def``
# factory shape (which is exactly Callable[..., Coroutine[...]]).


def async_transient[**P, R](
    fn: Callable[P, Coroutine[Any, Any, R]],
) -> Callable[P, Coroutine[Any, Any, R]]:
    """Tag an async ``fn`` as a ``TRANSIENT`` factory."""
    return _tag(fn, Lifecycle.TRANSIENT)


def async_singleton[**P, R](
    fn: Callable[P, Coroutine[Any, Any, R]],
) -> Callable[P, Coroutine[Any, Any, R]]:
    """Tag an async ``fn`` as a ``SINGLETON`` factory."""
    return _tag(fn, Lifecycle.SINGLETON)


def async_scoped[**P, R](
    fn: Callable[P, Coroutine[Any, Any, R]],
) -> Callable[P, Coroutine[Any, Any, R]]:
    """Tag an async ``fn`` as a ``SCOPED`` factory."""
    return _tag(fn, Lifecycle.SCOPED)
