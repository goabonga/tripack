# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Unit tests for the resolution context module."""

from __future__ import annotations

import asyncio

import pytest

from tripack_runtime.context import (
    ResolutionContext,
    aresolution_scope,
    current_context,
    resolution_scope,
)


class _Clock:
    """Framework-neutral token used across these tests."""


class _Cache:
    """A second token, used to test nested resolution stacks."""


def test_new_context_is_empty() -> None:
    """A fresh :class:`ResolutionContext` carries no tokens."""
    ctx = ResolutionContext()
    assert ctx.stack == ()
    assert _Clock not in ctx


def test_resolving_pushes_token_for_block_duration() -> None:
    """``with ctx.resolving(token)`` pushes; exit pops."""
    ctx = ResolutionContext()
    with ctx.resolving(_Clock):
        inside = ctx.stack
        assert inside == (_Clock,)
        assert _Clock in ctx
    outside = ctx.stack
    assert outside == ()
    assert _Clock not in ctx


def test_resolving_nests_correctly() -> None:
    """Nested ``resolving`` builds and unwinds the stack in order."""
    ctx = ResolutionContext()
    with ctx.resolving(_Clock):
        with ctx.resolving(_Cache):
            inner = ctx.stack
            assert inner == (_Clock, _Cache)
        middle = ctx.stack
        assert middle == (_Clock,)
    outer = ctx.stack
    assert outer == ()


def test_resolving_unwinds_on_exception() -> None:
    """The token is popped even when the body raises."""
    ctx = ResolutionContext()
    with pytest.raises(RuntimeError, match="boom"), ctx.resolving(_Clock):
        raise RuntimeError("boom")
    assert ctx.stack == ()


def test_stack_returns_immutable_tuple() -> None:
    """``stack`` is a snapshot tuple, not a live reference."""
    ctx = ResolutionContext()
    with ctx.resolving(_Clock):
        snapshot = ctx.stack
        with ctx.resolving(_Cache):
            pass
        # snapshot stays as captured, despite the inner push/pop.
        assert snapshot == (_Clock,)


def test_context_uses_slots_not_dict() -> None:
    """``__slots__`` keeps the context free of per-instance ``__dict__``."""
    ctx = ResolutionContext()
    assert not hasattr(ctx, "__dict__")


def test_current_context_is_none_outside_any_scope() -> None:
    """Without an active scope, :func:`current_context` is ``None``."""
    assert current_context() is None


def test_resolution_scope_binds_current_context() -> None:
    """Inside the scope, :func:`current_context` returns the active one."""
    with resolution_scope() as ctx:
        assert current_context() is ctx


def test_resolution_scope_restores_previous_context_on_exit() -> None:
    """The scope context manager unwinds the ContextVar cleanly."""
    assert current_context() is None
    with resolution_scope():
        assert current_context() is not None
    assert current_context() is None


def test_resolution_scope_nests() -> None:
    """Nested ``resolution_scope`` calls produce independent contexts."""
    with resolution_scope() as outer:
        with resolution_scope() as inner:
            assert current_context() is inner
            assert inner is not outer
        assert current_context() is outer


async def _aresolution_scope_binds_current_context() -> bool:
    """Coroutine helper covered by :func:`test_aresolution_scope_binds`."""
    async with aresolution_scope() as ctx:
        return current_context() is ctx


def test_aresolution_scope_binds_current_context() -> None:
    """The async scope manager binds the same ContextVar correctly."""
    assert asyncio.run(_aresolution_scope_binds_current_context())


async def _aresolving_pushes_and_pops() -> tuple[
    tuple[object, ...], tuple[object, ...]
]:
    """Coroutine helper covered by :func:`test_aresolving_pushes_and_pops`."""
    async with aresolution_scope() as ctx:
        async with ctx.aresolving(_Clock):
            inside = ctx.stack
        outside = ctx.stack
    return inside, outside


def test_aresolving_pushes_and_pops() -> None:
    """``aresolving`` exhibits the same push/pop contract as the sync."""
    inside, outside = asyncio.run(_aresolving_pushes_and_pops())
    assert inside == (_Clock,)
    assert outside == ()


async def _raise_inside_aresolving(ctx: ResolutionContext) -> None:
    """Single-statement helper used by the exception-unwinding test.

    Extracted so the surrounding ``pytest.raises`` body contains
    exactly one statement (pytest's PT012 lint rule), keeping the
    test free of any ``# noqa`` escape hatch.
    """
    async with ctx.aresolving(_Clock):
        raise RuntimeError("boom")


async def _aresolving_unwinds_on_exception() -> tuple[object, ...]:
    """Coroutine helper covered by :func:`test_aresolving_unwinds_on_exception`."""
    async with aresolution_scope() as ctx:
        with pytest.raises(RuntimeError, match="boom"):
            await _raise_inside_aresolving(ctx)
        return ctx.stack


def test_aresolving_unwinds_on_exception() -> None:
    """The async ``aresolving`` pops the token even when the body raises."""
    stack = asyncio.run(_aresolving_unwinds_on_exception())
    assert stack == ()


async def _concurrent_coroutine(label: str) -> tuple[int, tuple[object, ...]]:
    """Coroutine helper covered by
    :func:`test_concurrent_coroutines_have_independent_contexts`.

    Yields once mid-resolution so the asyncio scheduler can run the
    sibling coroutine in between; the returned stack proves we never
    saw the sibling's token.
    """
    async with aresolution_scope() as ctx, ctx.aresolving(label):
        await asyncio.sleep(0)
        return id(ctx), ctx.stack


async def _run_two_concurrent() -> tuple[
    tuple[int, tuple[object, ...]], tuple[int, tuple[object, ...]]
]:
    """Run two coroutines under :func:`asyncio.gather`."""
    return await asyncio.gather(
        _concurrent_coroutine("A"),
        _concurrent_coroutine("B"),
    )


def test_concurrent_coroutines_have_independent_contexts() -> None:
    """Two coroutines launched concurrently observe their own stacks.

    This is the contextvars-based isolation guarantee: each task
    inherits a copy of the :class:`ContextVar`, so the resolution
    contexts they create are separate instances and their pushes
    do not leak across the ``await`` boundary.
    """
    (id_a, stack_a), (id_b, stack_b) = asyncio.run(_run_two_concurrent())
    assert id_a != id_b
    assert stack_a == ("A",)
    assert stack_b == ("B",)
