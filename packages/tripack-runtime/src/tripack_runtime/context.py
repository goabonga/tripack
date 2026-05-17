# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Resolution context - tracks tokens currently being resolved.

A :class:`ResolutionContext` is the per-resolution scratchpad the
resolver maintains for one in-flight ``resolve()`` (or
``aresolve()``) operation. For now it carries only the resolution
stack, which the cycle detector inspects to spot ``A -> B -> A``
patterns; later commits attach scope membership and the per-scope
closeables list to the same context.

The context lives behind a :class:`contextvars.ContextVar`, so two
coroutines running concurrently via :func:`asyncio.gather` each get
their own copy. The :func:`resolution_scope` / :func:`aresolution_scope`
context managers are the entry points; everything below assumes the
caller has wrapped the resolve operation in one of them.

This module's public surface:

- :class:`ResolutionContext` - the data type the resolver receives.
- :func:`resolution_scope` - sync context manager that enters a
  fresh context and binds it as the current.
- :func:`aresolution_scope` - the awaitable counterpart.
- :func:`current_context` - accessor for the active context, returns
  ``None`` if no resolution is in flight on the current execution.
"""

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar

from tripack_contracts import DependencyToken


class ResolutionContext:
    """The per-resolution stack of tokens currently being resolved.

    A :class:`ResolutionContext` is mutable from within the runtime
    only - external consumers see a tuple snapshot via
    :attr:`stack` and a membership check via ``in``. Push/pop is
    handled exclusively through the :meth:`resolving` /
    :meth:`aresolving` context managers, which guarantee that the
    stack is unwound even when the wrapped body raises.

    Example::

        from tripack_runtime import ResolutionContext


        ctx = ResolutionContext()
        with ctx.resolving(Clock):
            assert Clock in ctx
            assert ctx.stack == (Clock,)
            with ctx.resolving(Cache):
                assert ctx.stack == (Clock, Cache)
        assert ctx.stack == ()
    """

    __slots__ = ("_stack",)

    def __init__(self) -> None:
        """Create a fresh empty context."""
        self._stack: list[DependencyToken] = []

    @property
    def stack(self) -> tuple[DependencyToken, ...]:
        """Snapshot of the current resolution stack (oldest first)."""
        return tuple(self._stack)

    def __contains__(self, token: object) -> bool:
        """Return whether ``token`` is currently being resolved."""
        return token in self._stack

    @contextmanager
    def resolving(self, token: DependencyToken) -> Iterator[None]:
        """Push ``token`` onto the stack for the duration of the block.

        The token is popped on exit even when the body raises, so
        the stack stays consistent with the call chain.
        """
        self._stack.append(token)
        try:
            yield
        finally:
            self._stack.pop()

    @asynccontextmanager
    async def aresolving(self, token: DependencyToken) -> AsyncIterator[None]:
        """Asynchronous counterpart of :meth:`resolving`.

        Same push/pop semantics; usable inside ``async def`` paths
        without polluting the sync API.
        """
        self._stack.append(token)
        try:
            yield
        finally:
            self._stack.pop()


_CURRENT_CONTEXT: ContextVar[ResolutionContext | None] = ContextVar(
    "tripack_resolution_context", default=None
)


def current_context() -> ResolutionContext | None:
    """Return the :class:`ResolutionContext` for the current execution.

    ``None`` when no resolution is in flight on the current sync
    thread or async task. Used by the resolver (and later by the
    cycle detector) to consult the in-flight stack.
    """
    return _CURRENT_CONTEXT.get()


@contextmanager
def resolution_scope() -> Iterator[ResolutionContext]:
    """Enter a fresh :class:`ResolutionContext` for the current thread.

    The new context becomes the value returned by
    :func:`current_context` until the block exits, at which point
    the previous value is restored.
    """
    ctx = ResolutionContext()
    token = _CURRENT_CONTEXT.set(ctx)
    try:
        yield ctx
    finally:
        _CURRENT_CONTEXT.reset(token)


@asynccontextmanager
async def aresolution_scope() -> AsyncIterator[ResolutionContext]:
    """Asynchronous counterpart of :func:`resolution_scope`.

    Each :class:`asyncio.Task` started inside the scope inherits a
    copy of the :class:`contextvars.ContextVar`, so concurrent
    resolutions launched via :func:`asyncio.gather` do not share
    their stacks.
    """
    ctx = ResolutionContext()
    token = _CURRENT_CONTEXT.set(ctx)
    try:
        yield ctx
    finally:
        _CURRENT_CONTEXT.reset(token)
