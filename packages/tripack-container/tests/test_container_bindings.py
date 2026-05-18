# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Unit tests for the :meth:`Container.bind` API (4.2)."""

from __future__ import annotations

import asyncio
from typing import assert_type

import pytest

from tripack_container import Container
from tripack_contracts import BindingError, Lifecycle, ResolutionError


class _Clock:
    """Framework-neutral token used as the canonical example."""


class _Cache:
    """A second token, used for SCOPED tests."""


def _make_clock_sync() -> _Clock:
    """Module-level sync factory: returns a fresh :class:`_Clock`."""
    return _Clock()


async def _make_clock_async() -> _Clock:
    """Module-level async factory: returns a fresh :class:`_Clock`."""
    return _Clock()


def test_bind_with_sync_factory_makes_token_resolvable() -> None:
    """After ``bind`` with a sync factory, ``resolve`` returns an instance."""
    container = Container()
    container.bind(_Clock, _make_clock_sync)
    instance = container.resolve(_Clock)
    assert isinstance(instance, _Clock)


async def _aresolve_after_async_bind() -> _Clock:
    """Helper: bind an async factory then drive ``aresolve``."""
    container = Container()
    container.bind(_Clock, _make_clock_async)
    return await container.aresolve(_Clock)


def test_bind_with_async_factory_makes_token_aresolve_able() -> None:
    """After ``bind`` with an async factory, ``aresolve`` returns an instance."""
    instance = asyncio.run(_aresolve_after_async_bind())
    assert isinstance(instance, _Clock)


def test_bind_with_async_factory_rejected_by_sync_resolve() -> None:
    """A bound async factory cannot be driven by the sync ``resolve``."""
    container = Container()
    container.bind(_Clock, _make_clock_async)
    with pytest.raises(ResolutionError, match="async-only"):
        container.resolve(_Clock)


def test_bind_is_idempotent_for_structurally_identical_bindings() -> None:
    """Re-binding the same factory under the same lifecycle is a no-op."""
    container = Container()
    container.bind(_Clock, _make_clock_sync, lifecycle=Lifecycle.SINGLETON)
    container.bind(_Clock, _make_clock_sync, lifecycle=Lifecycle.SINGLETON)
    # No exception means the second call was treated as identical.
    assert isinstance(container.resolve(_Clock), _Clock)


def test_bind_rejects_a_conflicting_lifecycle_on_the_same_token() -> None:
    """Two binds with the same token but different lifecycle raise BindingError."""
    container = Container()
    container.bind(_Clock, _make_clock_sync, lifecycle=Lifecycle.TRANSIENT)
    with pytest.raises(BindingError, match="Conflicting binding"):
        container.bind(_Clock, _make_clock_sync, lifecycle=Lifecycle.SINGLETON)


def test_bind_rejects_a_conflicting_factory_on_the_same_token() -> None:
    """Two binds with the same token but different factories raise BindingError.

    Smoke-invokes ``_other_factory`` before the conflict
    attempt so its body is covered: the bind raises before any
    resolution, so the factory would otherwise be dead code in
    this test.
    """

    def _other_factory() -> _Clock:
        return _Clock()

    assert isinstance(_other_factory(), _Clock)
    container = Container()
    container.bind(_Clock, _make_clock_sync)
    with pytest.raises(BindingError, match="Conflicting binding"):
        container.bind(_Clock, _other_factory)


def test_bind_singleton_lifecycle_caches_across_resolve_calls() -> None:
    """Binding with SINGLETON yields the cached instance on subsequent resolves."""
    container = Container()
    container.bind(_Clock, _make_clock_sync, lifecycle=Lifecycle.SINGLETON)
    first = container.resolve(_Clock)
    second = container.resolve(_Clock)
    assert first is second


def test_bind_scoped_lifecycle_caches_within_one_scope() -> None:
    """A SCOPED binding shares its instance for the duration of a scope.

    Uses :func:`tripack_runtime.lifetime_scope` directly here -
    the container exposes its own ``scope()`` helper in 4.7.
    """
    from tripack_runtime import lifetime_scope

    container = Container()
    container.bind(_Cache, _Cache, lifecycle=Lifecycle.SCOPED)
    with lifetime_scope():
        first = container.resolve(_Cache)
        second = container.resolve(_Cache)
    assert first is second


def test_bind_accepts_the_auto_inject_keyword() -> None:
    """``auto_inject=True`` is accepted now; full wiring lands in 4.6."""
    container = Container()
    container.bind(_Clock, _make_clock_sync, auto_inject=True)
    # Resolution still works in 4.2; the flag is stored, not yet acted on.
    assert isinstance(container.resolve(_Clock), _Clock)


def test_resolve_preserves_the_typed_return_via_assert_type() -> None:
    """Static check: ``Container.resolve(type[_Clock])`` is typed as ``_Clock``.

    The :func:`typing.assert_type` call is a no-op at runtime
    and a strict assertion in mypy. If a future refactor loses
    the generic parameter, mypy fails here before the consumer
    notices.
    """
    container = Container()
    container.bind(_Clock, _make_clock_sync)
    instance = container.resolve(_Clock)
    assert_type(instance, _Clock)


async def _aresolve_typed_return() -> _Clock:
    """Helper exercising the async-typed return."""
    container = Container()
    container.bind(_Clock, _make_clock_async)
    instance = await container.aresolve(_Clock)
    assert_type(instance, _Clock)
    return instance


def test_aresolve_preserves_the_typed_return_via_assert_type() -> None:
    """Static check on the async path."""
    instance = asyncio.run(_aresolve_typed_return())
    assert isinstance(instance, _Clock)
