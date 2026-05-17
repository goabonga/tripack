# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Closeable protocols - public teardown contract for stateful instances.

Any object the framework caches at the container or scope level
(singletons, scoped bindings) is inspected against
:class:`Closeable` and :class:`AsyncCloseable`. If it satisfies one,
the runtime registers it for teardown and calls ``close`` /
``aclose`` when the owning container or scope shuts down.

The contract is intentionally minimal:

- ``close()`` / ``aclose()`` take no arguments and return ``None``.
- They must be **idempotent**: calling them twice in a row is a
  no-op. The runtime cannot guarantee single invocation when an
  exception interrupts the teardown loop, so implementations are
  expected to track their own "already closed" state.
- They must NOT re-raise on already-closed input - swallowing a
  silent second call is the canonical safe behaviour.

The Protocol bodies raise :class:`NotImplementedError` defensively,
so accidental direct invocation on the Protocol class fails loud
instead of silently returning ``None``.
"""

from typing import Protocol


class Closeable(Protocol):
    """Synchronous teardown contract.

    A class satisfies :class:`Closeable` iff it exposes a no-arg
    method ``close`` returning ``None``::

        class FileHandle:
            def __init__(self, fp: object) -> None:
                self._fp = fp
                self._closed = False

            def close(self) -> None:
                if self._closed:
                    return
                # ... release resources ...
                self._closed = True

    The pattern is structurally compatible with
    :func:`contextlib.closing`, so any :class:`Closeable` can be used
    as a context manager without further adaptation.
    """

    def close(self) -> None:
        """Release any resources held by this instance.

        Must be idempotent: subsequent calls are no-ops, not errors.
        """
        raise NotImplementedError


class AsyncCloseable(Protocol):
    """Asynchronous teardown contract.

    The async counterpart of :class:`Closeable`. The method name is
    ``aclose`` (not ``close``) to match the convention used by
    :func:`contextlib.aclosing` and stdlib async generators.

    Example::

        class AsyncConnectionPool:
            def __init__(self) -> None:
                self._closed = False

            async def aclose(self) -> None:
                if self._closed:
                    return
                await self._drain_in_flight()
                self._closed = True
    """

    async def aclose(self) -> None:
        """Release any resources held by this instance.

        Must be idempotent: subsequent calls are no-ops, not errors.
        """
        raise NotImplementedError
