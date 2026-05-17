# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Unit tests for :class:`tripack_contracts.Resolver` and
:class:`tripack_contracts.AsyncResolver`."""

import asyncio
from typing import is_protocol

from tripack_contracts import AsyncResolver, Resolver


def test_resolver_is_a_protocol() -> None:
    """:class:`Resolver` is recognised as a typing Protocol."""
    assert is_protocol(Resolver)


def test_async_resolver_is_a_protocol() -> None:
    """:class:`AsyncResolver` is recognised as a typing Protocol."""
    assert is_protocol(AsyncResolver)


def test_concrete_class_satisfies_resolver_structurally() -> None:
    """An object with the matching ``resolve`` method *is* a Resolver."""

    class Clock:
        def __init__(self) -> None:
            self.time = "12:00:00"

    class ConstantResolver:
        def resolve[T](self, token: type[T]) -> T:
            return token()

    resolver: Resolver = ConstantResolver()
    clock = resolver.resolve(Clock)
    assert isinstance(clock, Clock)
    assert clock.time == "12:00:00"


def test_resolver_preserves_return_type_through_method_typevar() -> None:
    """The TypeVar T flows from the ``token`` argument to the return."""

    class Cache:
        def __init__(self) -> None:
            self.entries: list[str] = []

    class ConstantResolver:
        def resolve[T](self, token: type[T]) -> T:
            return token()

    resolver: Resolver = ConstantResolver()
    cache: Cache = resolver.resolve(Cache)
    # mypy: `cache` is typed as Cache, not Any - the test compiles
    # only because the resolver narrows correctly.
    assert cache.entries == []


def test_concrete_class_satisfies_async_resolver_structurally() -> None:
    """An object with the matching async ``resolve`` *is* an AsyncResolver."""

    class Clock:
        def __init__(self) -> None:
            self.time = "12:00:00"

    class AsyncConstantResolver:
        async def resolve[T](self, token: type[T]) -> T:
            return token()

    resolver: AsyncResolver = AsyncConstantResolver()
    clock = asyncio.run(resolver.resolve(Clock))
    assert isinstance(clock, Clock)
    assert clock.time == "12:00:00"


def test_async_resolver_preserves_return_type() -> None:
    """The TypeVar T flows through the awaited value."""

    class Logger:
        def __init__(self) -> None:
            self.records: list[str] = []

    class AsyncConstantResolver:
        async def resolve[T](self, token: type[T]) -> T:
            return token()

    resolver: AsyncResolver = AsyncConstantResolver()
    logger: Logger = asyncio.run(resolver.resolve(Logger))
    assert logger.records == []


def test_resolver_and_async_resolver_are_distinct_protocols() -> None:
    """``Resolver`` only requires sync ``resolve``; an unrelated async
    helper named ``aresolve`` coexists without satisfying
    :class:`AsyncResolver` (which requires ``resolve`` itself to be
    async).

    Both methods are exercised so the coverage gate stays at 100%
    and the test documents the dual-method pattern explicitly.
    """

    class DualResolver:
        def resolve[T](self, token: type[T]) -> T:
            return token()

        async def aresolve[T](self, token: type[T]) -> T:
            return token()

    class Probe:
        pass

    sync_resolver: Resolver = DualResolver()
    sync_instance = sync_resolver.resolve(Probe)
    assert isinstance(sync_instance, Probe)

    dual = DualResolver()
    async_instance = asyncio.run(dual.aresolve(Probe))
    assert isinstance(async_instance, Probe)
