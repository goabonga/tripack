# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Resolver protocols - the public lookup surface.

A resolver answers "give me the instance currently bound to this
token". Users of the framework program against a :class:`Resolver`
(or :class:`AsyncResolver`) rather than against the concrete
container, so test doubles can swap the wiring without touching the
consumer.

The synchronous variant is :class:`Resolver`; the asynchronous variant
is :class:`AsyncResolver`. Both expose a single ``resolve`` method
whose :class:`TypeVar` is declared at the method level (PEP 695
method-generic syntax), so the inferred return type matches the
class passed as the token::

    clock: Clock = resolver.resolve(Clock)   # type-checked

The method bodies raise :class:`NotImplementedError` defensively;
direct invocation on the Protocol class itself is never the intended
path - concrete implementations supply the lookup logic.
"""

from typing import Protocol


class Resolver(Protocol):
    """Synchronous resolution of a token to an instance of its type.

    A class satisfies :class:`Resolver` iff it exposes ``resolve``
    with the signature ``resolve[T](self, token: type[T]) -> T``::

        class ConstantResolver:
            def resolve[T](self, token: type[T]) -> T:
                return token()

        resolver: Resolver = ConstantResolver()
        clock = resolver.resolve(Clock)
    """

    def resolve[T](self, token: type[T]) -> T:
        """Return the instance currently bound to ``token``."""
        raise NotImplementedError


class AsyncResolver(Protocol):
    """Asynchronous resolution of a token to an instance of its type.

    The async counterpart of :class:`Resolver`. The contract is
    identical except that ``resolve`` is a coroutine, so consumers
    that already live on the event loop can chain resolutions
    without paying the sync/async bridge::

        class AsyncConstantResolver:
            async def resolve[T](self, token: type[T]) -> T:
                return token()

        resolver: AsyncResolver = AsyncConstantResolver()
        clock = await resolver.resolve(Clock)
    """

    async def resolve[T](self, token: type[T]) -> T:
        """Return the instance currently bound to ``token``."""
        raise NotImplementedError
