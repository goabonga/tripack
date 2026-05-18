# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Domain services for the Click + Tripack example."""

import time


class Clock:
    """Wall-clock service. ``now()`` returns a POSIX timestamp."""

    def now(self) -> float:
        """Return :func:`time.time` as a POSIX timestamp."""
        return time.time()


class EventLog:
    """In-memory append-only event store; SINGLETON-scoped."""

    def __init__(self) -> None:
        """Initialise with no recorded entries."""
        self._events: list[tuple[float, str]] = []

    def record(self, when: float, message: str) -> None:
        """Append one ``(timestamp, message)`` tuple."""
        self._events.append((when, message))

    def all(self) -> list[tuple[float, str]]:
        """Return a snapshot copy of the recorded entries."""
        return list(self._events)
