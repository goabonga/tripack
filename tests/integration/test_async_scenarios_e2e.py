# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""End-to-end async scenarios (aresolve, ascope, aclose, gather isolation)."""

from __future__ import annotations

import asyncio

import _fixtures as F

from tripack_container import ContainerBuilder
from tripack_contracts import Lifecycle


async def _aresolve_async_singleton() -> tuple[F.Clock, F.Clock]:
    """Coroutine helper: build a SINGLETON via async factory, resolve twice."""
    container = (
        ContainerBuilder()
        .bind(F.Clock, F.make_clock_async, lifecycle=Lifecycle.SINGLETON)
        .build()
    )
    first = await container.aresolve(F.Clock)
    second = await container.aresolve(F.Clock)
    return first, second


def test_async_factory_with_singleton_lifecycle_caches_canonical_instance() -> None:
    """Two ``aresolve`` of a SINGLETON yield the same instance."""
    first, second = asyncio.run(_aresolve_async_singleton())
    assert first is second


async def _ascope_with_async_close() -> int:
    """Coroutine helper: scope a Pool, exit the async scope, observe close count."""

    class AsyncPool:
        """Async-closeable resource that records its aclose call."""

        def __init__(self) -> None:
            self.aclose_calls = 0

        async def aclose(self) -> None:
            self.aclose_calls += 1

    container = (
        ContainerBuilder()
        .bind(AsyncPool, AsyncPool, lifecycle=Lifecycle.SCOPED)
        .build()
    )
    async with container.ascope():
        pool = container.resolve(AsyncPool)
    # ascope exit awaited pool.aclose() once.
    return pool.aclose_calls


def test_async_scope_exit_awaits_async_close_on_scoped_targets() -> None:
    """``async with container.ascope():`` awaits ``aclose`` on exit."""
    assert asyncio.run(_ascope_with_async_close()) == 1


async def _concurrent_singleton_resolves() -> tuple[F.Clock, F.Clock]:
    """Coroutine helper: two concurrent ``aresolve`` tasks of the same SINGLETON.

    Demonstrates the idempotent-registration guard end-to-end:
    even when both factory invocations complete, the container
    returns the same canonical instance to both racers.
    """
    can_finish = asyncio.Event()

    async def _slow_factory() -> F.Clock:
        await can_finish.wait()
        return F.Clock()

    container = (
        ContainerBuilder()
        .bind(F.Clock, _slow_factory, lifecycle=Lifecycle.SINGLETON)
        .build()
    )
    task_a = asyncio.create_task(container.aresolve(F.Clock))
    task_b = asyncio.create_task(container.aresolve(F.Clock))
    # Let both tasks reach the factory's await point.
    for _ in range(5):
        await asyncio.sleep(0)
    can_finish.set()
    return await asyncio.gather(task_a, task_b)


def test_concurrent_aresolve_of_a_singleton_returns_canonical_instance() -> None:
    """The race-safety guard fires through the full Container.aresolve path."""
    a, b = asyncio.run(_concurrent_singleton_resolves())
    assert a is b
