# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Unit tests for :meth:`Container.close` / :meth:`Container.aclose` (4.8)."""

from __future__ import annotations

import asyncio

import pytest

from tripack_container import Container
from tripack_contracts import Lifecycle


def test_close_invokes_singleton_teardowns_in_lifo_order() -> None:
    """Explicit ``container.close()`` runs each SINGLETON close in reverse order."""
    log: list[str] = []

    class _First:
        """Records 'first' on close."""

        def close(self) -> None:
            log.append("first")

    class _Second:
        """Records 'second' on close."""

        def close(self) -> None:
            log.append("second")

    container = Container()
    container.bind(_First, _First, lifecycle=Lifecycle.SINGLETON)
    container.bind(_Second, _Second, lifecycle=Lifecycle.SINGLETON)
    container.resolve(_First)
    container.resolve(_Second)
    container.close()
    assert log == ["second", "first"]


def test_close_is_idempotent_on_second_call() -> None:
    """A second ``close`` after the first is a no-op."""
    log: list[str] = []

    class _Service:
        """Single SINGLETON Closeable for the idempotence test."""

        def close(self) -> None:
            log.append("once")

    container = Container()
    container.bind(_Service, _Service, lifecycle=Lifecycle.SINGLETON)
    container.resolve(_Service)
    container.close()
    container.close()
    assert log == ["once"]


def test_container_as_sync_context_manager_auto_closes_on_exit() -> None:
    """``with Container():`` invokes :meth:`close` automatically on exit."""
    log: list[str] = []

    class _Service:
        """Records 'closed' when its close is called."""

        def close(self) -> None:
            log.append("closed")

    with Container() as container:
        container.bind(_Service, _Service, lifecycle=Lifecycle.SINGLETON)
        container.resolve(_Service)
    assert log == ["closed"]


def test_container_context_manager_closes_even_when_body_raises() -> None:
    """Auto-close runs on the error path too."""
    log: list[str] = []

    class _Service:
        """Records 'closed' on close even on error paths."""

        def close(self) -> None:
            log.append("closed")

    with pytest.raises(RuntimeError, match="body"), Container() as container:
        container.bind(_Service, _Service, lifecycle=Lifecycle.SINGLETON)
        container.resolve(_Service)
        raise RuntimeError("body")
    assert log == ["closed"]


# --- async ----------------------------------------------------------------


async def _aclose_drives_singleton_teardown() -> list[str]:
    """Coroutine helper for the async-close LIFO test."""
    log: list[str] = []

    class _AsyncA:
        """Records 'a' on aclose."""

        async def aclose(self) -> None:
            log.append("a")

    class _AsyncB:
        """Records 'b' on aclose."""

        async def aclose(self) -> None:
            log.append("b")

    container = Container()
    container.bind(_AsyncA, _AsyncA, lifecycle=Lifecycle.SINGLETON)
    container.bind(_AsyncB, _AsyncB, lifecycle=Lifecycle.SINGLETON)
    container.resolve(_AsyncA)
    container.resolve(_AsyncB)
    await container.aclose()
    return log


def test_aclose_invokes_async_singleton_teardowns_in_lifo_order() -> None:
    """Explicit ``container.aclose()`` awaits each target's aclose in LIFO order."""
    log = asyncio.run(_aclose_drives_singleton_teardown())
    assert log == ["b", "a"]


async def _aclose_is_idempotent() -> list[str]:
    """Coroutine helper for the async-close idempotence test."""
    log: list[str] = []

    class _Once:
        """Records 'once' on aclose."""

        async def aclose(self) -> None:
            log.append("once")

    container = Container()
    container.bind(_Once, _Once, lifecycle=Lifecycle.SINGLETON)
    container.resolve(_Once)
    await container.aclose()
    await container.aclose()
    return log


def test_aclose_is_idempotent_on_second_call() -> None:
    """A second ``aclose`` after the first does nothing."""
    log = asyncio.run(_aclose_is_idempotent())
    assert log == ["once"]


async def _container_as_async_context_manager_auto_closes() -> list[str]:
    """Coroutine helper: ``async with Container():`` invokes aclose on exit."""
    log: list[str] = []

    class _Service:
        """Records 'aclosed' on aclose."""

        async def aclose(self) -> None:
            log.append("aclosed")

    async with Container() as container:
        container.bind(_Service, _Service, lifecycle=Lifecycle.SINGLETON)
        container.resolve(_Service)
    return log


def test_container_as_async_context_manager_auto_closes_on_exit() -> None:
    """``async with`` runs :meth:`aclose` automatically on exit."""
    log = asyncio.run(_container_as_async_context_manager_auto_closes())
    assert log == ["aclosed"]


async def _async_cm_closes_on_body_error() -> list[str]:
    """Coroutine helper: async-context-manager teardown on body exception."""
    log: list[str] = []

    class _Service:
        """Records 'aclosed' on aclose even when body raises."""

        async def aclose(self) -> None:
            log.append("aclosed")

    async def _go() -> None:
        async with Container() as container:
            container.bind(_Service, _Service, lifecycle=Lifecycle.SINGLETON)
            container.resolve(_Service)
            raise RuntimeError("body")

    with pytest.raises(RuntimeError, match="body"):
        await _go()
    return log


def test_async_context_manager_closes_even_when_body_raises() -> None:
    """Async-context-manager teardown runs on the error path too."""
    log = asyncio.run(_async_cm_closes_on_body_error())
    assert log == ["aclosed"]
