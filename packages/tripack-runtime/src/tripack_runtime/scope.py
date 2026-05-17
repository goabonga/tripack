# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Lifetime scopes - bounded caches for SCOPED bindings.

A :class:`Scope` is a unit of cached resolution: inside the
scope, ``SCOPED`` bindings resolve to a single shared instance,
and on exit, every cached instance exposing ``close`` or
``aclose`` is captured for the eventual teardown propagation
(3.9). This is the building block for request-scoped DI: a web
framework opens one scope per request, the resolver hands out
the same request-bound services inside that scope, and the
container shuts them down on response.

Sync and async entry points are mirrored:

- :func:`lifetime_scope` - sync context manager;
- :func:`alifetime_scope` - async counterpart.

Both back the same :class:`Scope` data structure and use the
same module-level :class:`contextvars.ContextVar`, so a factory
that recursively resolves a SCOPED token participates in the
same scope as its caller. Each :class:`asyncio.Task` started
inside the scope inherits its own copy of the ContextVar, so
concurrent :func:`asyncio.gather` calls open and close
independent scopes without interference.
"""

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar
from typing import Any, Final

from tripack_contracts import AsyncCloseable, Closeable, DependencyToken

_MISSING: Final[Any] = object()


def is_teardown_target(instance: Any) -> bool:
    """Whether ``instance`` exposes a callable ``close`` or ``aclose``.

    Duck-typing rather than ``isinstance`` because the contracts
    :class:`Closeable` / :class:`AsyncCloseable` Protocols are
    not ``@runtime_checkable``. Matches the spirit of structural
    typing: any object with the right method shape qualifies.
    """
    return callable(getattr(instance, "close", None)) or callable(
        getattr(instance, "aclose", None)
    )


class Scope:
    """A bounded cache and teardown registry for SCOPED instances.

    Constructed exclusively by :func:`lifetime_scope` /
    :func:`alifetime_scope`; users do not instantiate
    :class:`Scope` directly. The cache and teardown list survive
    the context manager's exit (so callers can inspect what was
    built inside the block), even though the backing
    :class:`ContextVar` is reset on exit.
    """

    __slots__ = ("_cache", "_teardowns")

    def __init__(self) -> None:
        """Start with empty cache and teardown list."""
        self._cache: dict[DependencyToken, Any] = {}
        self._teardowns: list[Closeable | AsyncCloseable] = []

    def lookup(self, token: DependencyToken) -> Any:
        """Return the cached instance for ``token`` or the missing sentinel.

        The sentinel is the module-level ``_MISSING`` object;
        callers compare with ``is`` to distinguish "not cached"
        from a legitimately cached ``None`` value.
        """
        return self._cache.get(token, _MISSING)

    def remember(self, token: DependencyToken, instance: Any) -> None:
        """Cache ``instance`` under ``token`` and register teardown if applicable."""
        self._cache[token] = instance
        if is_teardown_target(instance):
            self._teardowns.append(instance)

    def teardowns(self) -> tuple[Closeable | AsyncCloseable, ...]:
        """Snapshot of registered teardown targets in registration order.

        Returned as a tuple so callers cannot mutate the
        underlying list. Insertion order matches construction
        order; the teardown propagation (3.9) will iterate in
        reverse so dependents close before what they depend on.
        """
        return tuple(self._teardowns)


_CURRENT_SCOPE: ContextVar[Scope | None] = ContextVar(
    "tripack_lifetime_scope", default=None
)


def current_scope() -> Scope | None:
    """Return the active :class:`Scope` for the current execution.

    ``None`` when no scope is open on the current sync thread or
    async task. The resolver consults this to decide whether a
    SCOPED binding has a home; user code typically does not call
    it directly.
    """
    return _CURRENT_SCOPE.get()


@contextmanager
def lifetime_scope() -> Iterator[Scope]:
    """Open a fresh :class:`Scope` and bind it as the current one.

    Inside the block, :func:`current_scope` returns the new
    instance; on exit the previous value (typically ``None``) is
    restored. Nested scopes work as expected: the inner one
    shadows the outer for the duration of its block, and the
    outer is restored on exit.
    """
    s = Scope()
    token = _CURRENT_SCOPE.set(s)
    try:
        yield s
    finally:
        _CURRENT_SCOPE.reset(token)


@asynccontextmanager
async def alifetime_scope() -> AsyncIterator[Scope]:
    """Asynchronous counterpart of :func:`lifetime_scope`.

    Each :class:`asyncio.Task` opened inside the surrounding
    context inherits a copy of the backing
    :class:`contextvars.ContextVar`, so concurrent
    :func:`asyncio.gather` calls each open and close their own
    independent scope without sharing the cache.
    """
    s = Scope()
    token = _CURRENT_SCOPE.set(s)
    try:
        yield s
    finally:
        _CURRENT_SCOPE.reset(token)
