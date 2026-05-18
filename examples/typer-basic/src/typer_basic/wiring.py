# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Container assembly for the Typer + Tripack example."""

from tripack_container import Container, ContainerBuilder
from tripack_contracts import Lifecycle
from typer_basic.services import Clock, EventLog


def build_container() -> Container:
    """Return a sealed :class:`Container` wired for the CLI.

    Two bindings, both ``SINGLETON``:

    - :class:`Clock`    - one wall-clock for the CLI invocation.
    - :class:`EventLog` - shared in-memory log, accumulates
      across ``record`` calls within a single CLI session.
    """
    return (
        ContainerBuilder()
        .bind(Clock, Clock, lifecycle=Lifecycle.SINGLETON)
        .bind(EventLog, EventLog, lifecycle=Lifecycle.SINGLETON)
        .build()
    )
