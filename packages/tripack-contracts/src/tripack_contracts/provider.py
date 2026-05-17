# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Provider protocols - factories the runtime invokes to produce a `T`.

A provider is a callable-like object that the runtime asks for "an
instance of ``T``". The synchronous variant lives at
:class:`Provider`; the asynchronous variant at :class:`AsyncProvider`.

Both are :class:`typing.Protocol` subclasses, so any object with a
matching ``provide`` method satisfies the contract structurally - no
inheritance required. Their method bodies raise
:class:`NotImplementedError` defensively: direct invocation on the
Protocol class itself is never the intended path. Concrete
implementations supply their own bodies.
"""

from typing import Protocol


class Provider[T](Protocol):
    """Synchronous factory of ``T``.

    A class satisfies :class:`Provider[T]` iff it exposes a no-arg
    method ``provide`` returning ``T``::

        class SystemClock:
            def provide(self) -> str:
                return "12:00:00"

        clock_provider: Provider[str] = SystemClock()
    """

    def provide(self) -> T:
        """Return an instance of ``T``."""
        raise NotImplementedError


class AsyncProvider[T](Protocol):
    """Asynchronous factory of ``T``.

    The async counterpart of :class:`Provider`. Use when the factory
    needs to await I/O - opening a database connection, fetching a
    remote secret, performing handshakes::

        class AsyncSystemClock:
            async def provide(self) -> str:
                await some_io()
                return "12:00:00"

        clock_provider: AsyncProvider[str] = AsyncSystemClock()
    """

    async def provide(self) -> T:
        """Return an instance of ``T``."""
        raise NotImplementedError
