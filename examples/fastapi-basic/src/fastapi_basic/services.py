# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Concrete implementations of the interfaces in ``contracts.py``.

Each class satisfies one of the ``Protocol`` interfaces and is
bound under that interface in :file:`container.json`. The
handlers in :mod:`fastapi_basic.api` never reference these
classes directly - they only see the interface tokens via
``Annotated[T, Inject]``.
"""

import time
import uuid

from fastapi_basic.contracts import Clock, EventLog


class SystemClock:
    """``Clock`` impl that reads :func:`time.time`."""

    def now(self) -> float:
        """Return the wall-clock POSIX timestamp."""
        return time.time()


class Uuid4RequestId:
    """``RequestId`` impl: minted from :func:`uuid.uuid4` once per scope."""

    def __init__(self) -> None:
        """Generate a fresh UUID v4 hex string at construction."""
        self.value = str(uuid.uuid4())


class InMemoryEventLog:
    """``EventLog`` impl with an append-only in-memory list."""

    def __init__(self) -> None:
        """Initialise an empty event list."""
        self._events: list[tuple[float, str, str]] = []

    def record(self, when: float, request_id: str, message: str) -> None:
        """Append a ``(when, request_id, message)`` triple."""
        self._events.append((when, request_id, message))

    def all(self) -> list[tuple[float, str, str]]:
        """Return a shallow copy of the accumulated entries."""
        return list(self._events)


class DefaultAuditTrail:
    """``AuditTrail`` impl that depends on two **interfaces**.

    The constructor signature names ``Clock`` and
    ``EventLog`` - both ``Protocol``s - and the JSON binding
    sets ``auto_inject=true``. At resolve time the container
    introspects this ``__init__``, looks up the bindings for
    each interface, and supplies them. Neither this class nor
    the handler that calls :meth:`trace` is aware of which
    concrete impl is wired behind the scenes.
    """

    def __init__(self, clock: Clock, log: EventLog) -> None:
        """Capture references to the resolved interface implementations."""
        self._clock = clock
        self._log = log

    def trace(self, request_id: str, action: str) -> None:
        """Record an audit entry under the active request id."""
        self._log.record(self._clock.now(), request_id, f"audit:{action}")
