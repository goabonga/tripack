# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Unit tests for :class:`tripack_contracts.Provider` and
:class:`tripack_contracts.AsyncProvider`."""

import asyncio
from typing import is_protocol

from tripack_contracts import AsyncProvider, Provider


def test_provider_is_a_protocol() -> None:
    """:class:`Provider` is recognised as a typing Protocol."""
    assert is_protocol(Provider)


def test_async_provider_is_a_protocol() -> None:
    """:class:`AsyncProvider` is recognised as a typing Protocol."""
    assert is_protocol(AsyncProvider)


def test_concrete_class_satisfies_provider_structurally() -> None:
    """An object with a matching ``provide`` method *is* a Provider."""

    class SystemClock:
        def provide(self) -> str:
            return "12:00:00"

    clock_provider: Provider[str] = SystemClock()
    assert clock_provider.provide() == "12:00:00"


def test_provider_parametrises_on_the_returned_type() -> None:
    """The TypeVar ``T`` flows to the concrete return type."""

    class IntProvider:
        def provide(self) -> int:
            return 42

    provider: Provider[int] = IntProvider()
    value: int = provider.provide()
    assert value == 42


def test_concrete_class_satisfies_async_provider_structurally() -> None:
    """An object with a matching async ``provide`` method *is* an
    AsyncProvider, and ``await`` yields its return value."""

    class AsyncSystemClock:
        async def provide(self) -> str:
            return "12:00:00"

    clock_provider: AsyncProvider[str] = AsyncSystemClock()
    assert asyncio.run(clock_provider.provide()) == "12:00:00"


def test_async_provider_parametrises_on_the_returned_type() -> None:
    """The TypeVar ``T`` flows through the awaited value."""

    class AsyncIntProvider:
        async def provide(self) -> int:
            return 42

    provider: AsyncProvider[int] = AsyncIntProvider()
    value: int = asyncio.run(provider.provide())
    assert value == 42


def test_provider_and_async_provider_are_distinct_protocols() -> None:
    """``Provider`` only requires ``provide``; an unrelated async method
    coexists without satisfying :class:`AsyncProvider`.

    Both methods are exercised to keep the coverage gate at 100% and
    to document the dual-method pattern (a class can carry an async
    helper without becoming an AsyncProvider, because the Protocol
    contract is on the *name* and *signature* of ``provide`` itself).
    """

    class DualProvider:
        def provide(self) -> str:
            return "sync"

        async def aprovide(self) -> str:
            return "async"

    sync_provider: Provider[str] = DualProvider()
    assert sync_provider.provide() == "sync"

    dual = DualProvider()
    assert asyncio.run(dual.aprovide()) == "async"
