# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Unit tests for the cycle-detection module."""

from __future__ import annotations

import asyncio

import pytest

from tripack_contracts import CircularDependencyError
from tripack_runtime.context import ResolutionContext
from tripack_runtime.cycles import (
    aguarded_resolving,
    check_for_cycle,
    guarded_resolving,
)


class _Clock:
    """Framework-neutral token used as a class-shaped dependency."""


class _Cache:
    """A second class token, used for multi-step cycles."""


class _Logger:
    """A third class token, used for >2-step cycles."""


def test_check_for_cycle_is_a_noop_on_empty_stack() -> None:
    """An empty context never reports a cycle."""
    ctx = ResolutionContext()
    check_for_cycle(ctx, _Clock)
    assert ctx.stack == ()


def test_check_for_cycle_is_a_noop_when_token_not_on_stack() -> None:
    """A token absent from the stack is not a cycle."""
    ctx = ResolutionContext()
    with ctx.resolving(_Clock):
        check_for_cycle(ctx, _Cache)
        inside = ctx.stack
        assert inside == (_Clock,)


def test_check_for_cycle_raises_on_self_loop() -> None:
    """Re-entering the same token raises with a length-2 cycle."""
    ctx = ResolutionContext()
    with ctx.resolving(_Clock), pytest.raises(CircularDependencyError) as exc_info:
        check_for_cycle(ctx, _Clock)
    assert exc_info.value.cycle == (_Clock, _Clock)


def test_check_for_cycle_reports_the_full_loop() -> None:
    """A multi-step cycle is reported from first occurrence to close."""
    ctx = ResolutionContext()
    with (
        ctx.resolving(_Clock),
        ctx.resolving(_Cache),
        ctx.resolving(_Logger),
        pytest.raises(CircularDependencyError) as exc_info,
    ):
        check_for_cycle(ctx, _Clock)
    assert exc_info.value.cycle == (_Clock, _Cache, _Logger, _Clock)


def test_check_for_cycle_starts_at_the_first_occurrence() -> None:
    """A cycle entry deep in the stack reports only the closing segment."""
    ctx = ResolutionContext()
    with (
        ctx.resolving(_Logger),
        ctx.resolving(_Clock),
        ctx.resolving(_Cache),
        pytest.raises(CircularDependencyError) as exc_info,
    ):
        check_for_cycle(ctx, _Clock)
    # Logger sits below the cycle entry point; it is not part of the loop.
    assert exc_info.value.cycle == (_Clock, _Cache, _Clock)


def test_check_for_cycle_leaves_the_stack_intact() -> None:
    """A failed check does not mutate the context."""
    ctx = ResolutionContext()
    with ctx.resolving(_Clock):
        before = ctx.stack
        with pytest.raises(CircularDependencyError):
            check_for_cycle(ctx, _Clock)
        after = ctx.stack
    assert before == (_Clock,)
    assert after == (_Clock,)


def test_check_for_cycle_supports_string_tokens() -> None:
    """String tokens participate in cycle detection like classes."""
    ctx = ResolutionContext()
    with (
        ctx.resolving("primary-clock"),
        pytest.raises(CircularDependencyError) as exc_info,
    ):
        check_for_cycle(ctx, "primary-clock")
    assert exc_info.value.cycle == ("primary-clock", "primary-clock")


def test_check_for_cycle_message_contains_the_cycle_path() -> None:
    """The exception's string form renders the cycle in resolution order."""
    ctx = ResolutionContext()
    with (
        ctx.resolving(_Clock),
        ctx.resolving(_Cache),
        pytest.raises(CircularDependencyError, match="_Clock -> _Cache -> _Clock"),
    ):
        check_for_cycle(ctx, _Clock)


def test_guarded_resolving_pushes_and_pops_when_no_cycle() -> None:
    """The sync guard behaves like ``resolving`` on the happy path."""
    ctx = ResolutionContext()
    with guarded_resolving(ctx, _Clock):
        inside = ctx.stack
        assert inside == (_Clock,)
    assert ctx.stack == ()


def test_guarded_resolving_refuses_to_push_on_cycle() -> None:
    """A failed guard rejects on ``__enter__`` and leaves the stack intact.

    The body of a ``with guarded_resolving(...)`` block is never
    reached on the cycle path, which would leave an unreachable
    statement in the test. Driving ``__enter__`` directly keeps
    the test free of dead code while exercising the exact same
    rejection logic.
    """
    ctx = ResolutionContext()
    with ctx.resolving(_Clock):
        manager = guarded_resolving(ctx, _Clock)
        with pytest.raises(CircularDependencyError):
            manager.__enter__()
        snapshot = ctx.stack
        assert snapshot == (_Clock,)


async def _aguarded_happy_path() -> tuple[tuple[object, ...], tuple[object, ...]]:
    """Coroutine helper covered by :func:`test_aguarded_resolving_happy_path`."""
    ctx = ResolutionContext()
    async with aguarded_resolving(ctx, _Clock):
        inside = ctx.stack
    outside = ctx.stack
    return inside, outside


def test_aguarded_resolving_happy_path() -> None:
    """The async guard pushes on entry and pops on normal exit."""
    inside, outside = asyncio.run(_aguarded_happy_path())
    assert inside == (_Clock,)
    assert outside == ()


async def _aguarded_refuses_cycle() -> tuple[object, ...]:
    """Coroutine helper covered by :func:`test_aguarded_resolving_refuses_cycle`.

    Drives ``__aenter__`` directly for the same reason as the sync
    counterpart: the body of an ``async with`` block is never
    reached when the guard rejects, so going through the high-
    level form would leave dead code in the test.
    """
    ctx = ResolutionContext()
    async with ctx.aresolving(_Clock):
        manager = aguarded_resolving(ctx, _Clock)
        with pytest.raises(CircularDependencyError):
            await manager.__aenter__()
        return ctx.stack


def test_aguarded_resolving_refuses_cycle() -> None:
    """The async guard rejects re-entry without polluting the stack."""
    stack = asyncio.run(_aguarded_refuses_cycle())
    assert stack == (_Clock,)
