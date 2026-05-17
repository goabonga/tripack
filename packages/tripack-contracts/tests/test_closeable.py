# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Unit tests for :class:`tripack_contracts.Closeable` and
:class:`tripack_contracts.AsyncCloseable`."""

import asyncio
from contextlib import aclosing, closing
from typing import is_protocol

from tripack_contracts import AsyncCloseable, Closeable


def test_closeable_is_a_protocol() -> None:
    """:class:`Closeable` is recognised as a typing Protocol."""
    assert is_protocol(Closeable)


def test_async_closeable_is_a_protocol() -> None:
    """:class:`AsyncCloseable` is recognised as a typing Protocol."""
    assert is_protocol(AsyncCloseable)


def test_concrete_class_satisfies_closeable_structurally() -> None:
    """An object with a no-arg ``close`` method *is* a Closeable."""

    class FileHandle:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

    handle: Closeable = FileHandle()
    handle.close()
    # Static narrow: handle satisfies Closeable, dynamic call works.
    assert isinstance(handle, FileHandle)
    assert handle.closed is True


def test_concrete_class_satisfies_async_closeable_structurally() -> None:
    """An object with an async ``aclose`` method *is* an AsyncCloseable."""

    class AsyncPool:
        def __init__(self) -> None:
            self.closed = False

        async def aclose(self) -> None:
            self.closed = True

    pool: AsyncCloseable = AsyncPool()
    asyncio.run(pool.aclose())
    assert isinstance(pool, AsyncPool)
    assert pool.closed is True


def test_closeable_is_idempotent() -> None:
    """A well-formed ``close`` swallows redundant calls.

    The Protocol does not enforce idempotency, but implementations
    are expected to short-circuit on a second call. This test pins
    that expectation through a sample implementation.
    """

    class Counter:
        def __init__(self) -> None:
            self.close_calls = 0
            self._closed = False

        def close(self) -> None:
            if self._closed:
                return
            self.close_calls += 1
            self._closed = True

    counter: Closeable = Counter()
    counter.close()
    counter.close()
    counter.close()
    assert isinstance(counter, Counter)
    assert counter.close_calls == 1


def test_async_closeable_is_idempotent() -> None:
    """Idempotency expectation applies to the async variant too."""

    class AsyncCounter:
        def __init__(self) -> None:
            self.aclose_calls = 0
            self._closed = False

        async def aclose(self) -> None:
            if self._closed:
                return
            self.aclose_calls += 1
            self._closed = True

    async def run_thrice() -> AsyncCounter:
        counter = AsyncCounter()
        await counter.aclose()
        await counter.aclose()
        await counter.aclose()
        return counter

    counter = asyncio.run(run_thrice())
    assert counter.aclose_calls == 1


def test_closeable_works_with_contextlib_closing() -> None:
    """``contextlib.closing`` accepts any :class:`Closeable`."""

    class Resource:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

    resource = Resource()
    with closing(resource) as r:
        assert r.closed is False
    assert resource.closed is True


def test_async_closeable_works_with_contextlib_aclosing() -> None:
    """``contextlib.aclosing`` accepts any :class:`AsyncCloseable`."""

    class AsyncResource:
        def __init__(self) -> None:
            self.closed = False

        async def aclose(self) -> None:
            self.closed = True

    async def use_resource() -> AsyncResource:
        resource = AsyncResource()
        async with aclosing(resource) as r:
            assert r.closed is False
        return resource

    resource = asyncio.run(use_resource())
    assert resource.closed is True
