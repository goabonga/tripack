# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Lifetime scopes - bounded caches for SCOPED bindings.

A :class:`Scope` is a unit of cached resolution: inside the
scope, ``SCOPED`` bindings resolve to a single shared instance,
and on exit every cached instance exposing ``close`` or
``aclose`` is torn down. This is the building block for
request-scoped DI: a web framework opens one scope per request,
the resolver hands out the same request-bound services inside
that scope, and the framework closes them on response.

Sync and async entry points are mirrored:

- :func:`lifetime_scope` - sync context manager; auto-calls
  :meth:`Scope.close` on exit.
- :func:`alifetime_scope` - async counterpart; auto-awaits
  :meth:`Scope.aclose` on exit.

Both back the same :class:`Scope` data structure and use the
same module-level :class:`contextvars.ContextVar`, so a factory
that recursively resolves a SCOPED token participates in the
same scope as its caller. Each :class:`asyncio.Task` started
inside the scope inherits its own copy of the ContextVar, so
concurrent :func:`asyncio.gather` calls open and close
independent scopes without interference.

Teardown propagation iterates registered targets in **LIFO**
order (reverse of registration / construction order), so
dependents close before what they depend on. A single failing
``close`` / ``aclose`` does not prevent the others from
running; collected exceptions are surfaced as an
:class:`ExceptionGroup` at the end.
"""

from collections.abc import AsyncIterator, Iterator, Sequence
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar
from typing import Any, Final

from tripack_contracts import AsyncCloseable, Closeable, DependencyToken

_MISSING: Final[Any] = object()


def _close_all_sync(targets: Sequence[Closeable | AsyncCloseable]) -> None:
    """Invoke sync ``close()`` on each target in reverse order.

    Targets that expose only ``aclose`` (no ``close``) cannot be
    torn down on the sync path and are skipped silently; reach
    them via :func:`_close_all_async` instead. Errors raised by
    individual ``close`` calls are collected and surfaced as an
    :class:`ExceptionGroup` so a single failure does not prevent
    the rest of the list from being processed.
    """
    errors: list[Exception] = []
    for target in reversed(targets):
        close_method = getattr(target, "close", None)
        if callable(close_method):
            try:
                close_method()
            except Exception as exc:
                errors.append(exc)
    if errors:
        raise ExceptionGroup("Errors during teardown", errors)


async def _close_all_async(targets: Sequence[Closeable | AsyncCloseable]) -> None:
    """Invoke teardown on each target in reverse order, awaiting where needed.

    Prefers ``aclose`` when the target exposes it; falls back to
    sync ``close`` for sync-only targets. Errors are collected
    and surfaced as an :class:`ExceptionGroup` so a single
    failure does not prevent the rest of the list from being
    processed.
    """
    errors: list[Exception] = []
    for target in reversed(targets):
        aclose_method = getattr(target, "aclose", None)
        if callable(aclose_method):
            try:
                await aclose_method()
            except Exception as exc:
                errors.append(exc)
        else:
            close_method = getattr(target, "close", None)
            if callable(close_method):
                try:
                    close_method()
                except Exception as exc:
                    errors.append(exc)
    if errors:
        raise ExceptionGroup("Errors during teardown", errors)


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

    __slots__ = ("_cache", "_closed", "_teardowns")

    def __init__(self) -> None:
        """Start with empty cache and teardown list."""
        self._cache: dict[DependencyToken, Any] = {}
        self._teardowns: list[Closeable | AsyncCloseable] = []
        self._closed = False

    def lookup(self, token: DependencyToken) -> Any:
        """Return the cached instance for ``token`` or the missing sentinel.

        The sentinel is the module-level ``_MISSING`` object;
        callers compare with ``is`` to distinguish "not cached"
        from a legitimately cached ``None`` value.
        """
        return self._cache.get(token, _MISSING)

    def remember(self, token: DependencyToken, instance: Any) -> Any:
        """Cache ``instance`` under ``token`` and return the canonical entry.

        Idempotent: when ``token`` is already cached, the existing
        entry wins. The cache is not overwritten, the teardown
        list is not extended, and the existing instance is the
        return value. The supplied ``instance`` is discarded in
        that case - its lifetime is the caller's responsibility,
        since the runtime cannot retroactively close a value the
        factory already produced.

        This is the protection against double-registration races:
        two concurrent ``aresolve`` of the same SCOPED token can
        both pass the cache miss check and both invoke their
        factory; the first one to reach :meth:`remember` wins,
        and the second receives the same canonical instance the
        first one stored. Sync resolution is single-threaded
        within one task, so the race only matters for async.
        """
        if token in self._cache:
            return self._cache[token]
        self._cache[token] = instance
        if is_teardown_target(instance):
            self._teardowns.append(instance)
        return instance

    def teardowns(self) -> tuple[Closeable | AsyncCloseable, ...]:
        """Snapshot of registered teardown targets in registration order.

        Returned as a tuple so callers cannot mutate the
        underlying list. Insertion order matches construction
        order; :meth:`close` / :meth:`aclose` iterate it in
        reverse so dependents close before what they depend on.
        """
        return tuple(self._teardowns)

    def close(self) -> None:
        """Close every registered teardown target in LIFO order.

        Calls each target's ``close`` method in reverse order.
        Targets exposing only ``aclose`` (AsyncCloseable) cannot
        be torn down on the sync path and are skipped silently;
        use :meth:`aclose` to handle them. Errors raised by
        individual close calls are collected and surfaced as a
        single :class:`ExceptionGroup` at the end.

        Idempotent: a second call after the first is a no-op,
        guarded by an internal ``_closed`` flag. Each target's
        ``close`` is itself required to be idempotent by the
        :class:`Closeable` contract.
        """
        if self._closed:
            return
        try:
            _close_all_sync(self._teardowns)
        finally:
            self._closed = True

    async def aclose(self) -> None:
        """Asynchronously close every registered teardown target.

        Calls each target's ``aclose`` in reverse order, falling
        back to sync ``close`` for sync-only targets. Errors are
        collected and surfaced as a single
        :class:`ExceptionGroup` at the end. Idempotent the same
        way as :meth:`close`.
        """
        if self._closed:
            return
        try:
            await _close_all_async(self._teardowns)
        finally:
            self._closed = True


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
    restored AND :meth:`Scope.close` is invoked so every
    registered sync ``close`` runs. Async-only teardown targets
    (only ``aclose``) are skipped silently - reach them through
    :func:`alifetime_scope` instead. Nested scopes work as
    expected: the inner one shadows the outer for the duration
    of its block, and the outer is restored on exit.

    Teardown happens even when the body raises: an exception
    inside the block propagates normally after the scope's
    close has been attempted; an exception inside close is
    chained onto the body's via ``__context__``.
    """
    s = Scope()
    token = _CURRENT_SCOPE.set(s)
    try:
        yield s
    finally:
        _CURRENT_SCOPE.reset(token)
        s.close()


@asynccontextmanager
async def alifetime_scope() -> AsyncIterator[Scope]:
    """Asynchronous counterpart of :func:`lifetime_scope`.

    Each :class:`asyncio.Task` opened inside the surrounding
    context inherits a copy of the backing
    :class:`contextvars.ContextVar`, so concurrent
    :func:`asyncio.gather` calls each open and close their own
    independent scope without sharing the cache.

    On exit :meth:`Scope.aclose` is awaited so every registered
    ``aclose`` runs (with sync ``close`` as a fallback for
    sync-only targets). Teardown happens even when the body
    raises.
    """
    s = Scope()
    token = _CURRENT_SCOPE.set(s)
    try:
        yield s
    finally:
        _CURRENT_SCOPE.reset(token)
        await s.aclose()
