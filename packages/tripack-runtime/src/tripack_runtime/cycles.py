# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Cycle detection for in-flight resolutions.

When the resolver opens a frame for a token, the cycle detector
checks whether that token already appears on the active
:class:`ResolutionContext` stack. If it does, a
:class:`CircularDependencyError` is raised before the resolver
recurses into a factory that would otherwise never terminate.

The classic example is two services that depend on each other:

- a ``Cache`` factory needs a ``Clock`` to expire entries;
- the ``Clock`` factory accepts a ``Cache`` to memoise the
  last-tick value.

Without the guard, resolving ``Cache`` recurses into ``Clock``
which recurses into ``Cache`` and so on forever. The guard turns
that into a single error whose ``cycle`` attribute names the
full loop in resolution order.

The module's public surface:

- :func:`check_for_cycle` - the raw predicate; raises on cycle.
- :func:`guarded_resolving` - sync context manager that combines
  the check with :meth:`ResolutionContext.resolving`.
- :func:`aguarded_resolving` - the awaitable counterpart.
"""

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager

from tripack_contracts import CircularDependencyError, DependencyToken
from tripack_runtime.context import ResolutionContext


def check_for_cycle(ctx: ResolutionContext, token: DependencyToken) -> None:
    """Raise :class:`CircularDependencyError` if ``token`` is already on the stack.

    The reported cycle is the slice of the stack starting at the
    first occurrence of ``token`` and closing with ``token`` itself,
    so a user observes ``A -> B -> A`` rather than ``B -> A`` or
    ``A`` alone. The check is non-mutating: a successful call (no
    cycle) leaves the context untouched, and a failing call raises
    before any state changes elsewhere.
    """
    stack = ctx.stack
    if token in stack:
        idx = stack.index(token)
        cycle = stack[idx:] + (token,)
        raise CircularDependencyError(cycle)


@contextmanager
def guarded_resolving(ctx: ResolutionContext, token: DependencyToken) -> Iterator[None]:
    """Run a sync resolution frame for ``token``, refusing cycles.

    Equivalent to ``with ctx.resolving(token):`` preceded by a
    :func:`check_for_cycle` call. The check happens before the
    push, so a failed guard does not leak a partial frame onto
    the stack.
    """
    check_for_cycle(ctx, token)
    with ctx.resolving(token):
        yield


@asynccontextmanager
async def aguarded_resolving(
    ctx: ResolutionContext, token: DependencyToken
) -> AsyncIterator[None]:
    """Asynchronous counterpart of :func:`guarded_resolving`."""
    check_for_cycle(ctx, token)
    async with ctx.aresolving(token):
        yield
