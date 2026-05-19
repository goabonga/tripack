# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Interfaces (``Protocol``) the FastAPI handlers depend on.

Each binding in :file:`container.json` maps one of these
interfaces to a concrete implementation from
:mod:`fastapi_basic.services`. The handlers in
:mod:`fastapi_basic.api` reference only the interfaces - they
never import the concrete classes, so swapping an
implementation (or wiring a fake one in tests) is a one-line
config change with no handler rewrite.
"""

from typing import Protocol


class Clock(Protocol):
    """Wall-clock reader. SINGLETON in the default wiring."""

    def now(self) -> float:
        """Return a POSIX timestamp."""
        ...


class RequestId(Protocol):
    """Per-request identifier. SCOPED in the default wiring.

    Read as ``rid.value`` so the interface is callable-free -
    a plain attribute on the implementation is enough.
    """

    value: str


class EventLog(Protocol):
    """In-memory event store. SINGLETON in the default wiring."""

    def record(self, when: float, request_id: str, message: str) -> None:
        """Append one entry to the log."""
        ...

    def all(self) -> list[tuple[float, str, str]]:
        """Snapshot copy of the accumulated entries."""
        ...


class AuditTrail(Protocol):
    """Audits actions; depends on :class:`Clock` and :class:`EventLog`.

    Implementations declare those two interfaces as constructor
    parameters and the container resolves them via
    ``auto_inject=true`` at construction time. The handler that
    consumes :class:`AuditTrail` never sees ``Clock`` or
    ``EventLog`` directly.
    """

    def trace(self, request_id: str, action: str) -> None:
        """Emit an audit entry for the given request + action."""
        ...


class Notifier(Protocol):
    """Optional notifier sink.

    Bindings for this interface are intentionally omitted from
    the default :file:`container.json`. The handler reads it as
    ``Notifier | None`` so a missing binding short-circuits to
    ``None`` instead of raising.
    """

    def notify(self, message: str) -> None:
        """Deliver ``message`` to whatever sink the impl backs."""
        ...
