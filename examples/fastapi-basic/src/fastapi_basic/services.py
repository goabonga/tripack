# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Domain services for the FastAPI + Tripack example.

Three deliberately tiny services to keep the focus on the
wiring rather than the business logic:

- :class:`Clock` reads the wall clock (SINGLETON, shared by
  every request).
- :class:`RequestId` mints a fresh identifier (SCOPED, one
  per HTTP request via the lifespan + middleware combo).
- :class:`EventLog` accumulates entries in-memory (SINGLETON,
  shared by every request, but a real app would back it with
  Redis or a database).
"""

import time
import uuid


class Clock:
    """Wall-clock service. ``now()`` returns a POSIX timestamp."""

    def now(self) -> float:
        """Return :func:`time.time` as a POSIX timestamp."""
        return time.time()


class RequestId:
    """Per-request identifier; bound under :data:`Lifecycle.SCOPED`."""

    def __init__(self) -> None:
        """Mint a UUID v4 once per scope."""
        self.value = str(uuid.uuid4())


class EventLog:
    """In-memory append-only event store.

    Bound under :data:`Lifecycle.SINGLETON` so every request
    sees the same log. Each ``record`` call appends a
    ``(timestamp, request_id, message)`` triple; ``all``
    returns the accumulated list as tuples.
    """

    def __init__(self) -> None:
        """Initialise an empty in-memory list."""
        self._events: list[tuple[float, str, str]] = []

    def record(self, when: float, request_id: str, message: str) -> None:
        """Append one entry to the log."""
        self._events.append((when, request_id, message))

    def all(self) -> list[tuple[float, str, str]]:
        """Return a snapshot copy of every recorded entry."""
        return list(self._events)
