# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Container assembly for the Click + Tripack example."""

from click_basic.services import Clock, EventLog
from tripack_container import Container, ContainerBuilder
from tripack_contracts import Lifecycle


def build_container() -> Container:
    """Return a sealed :class:`Container` for the CLI demo."""
    return (
        ContainerBuilder()
        .bind(Clock, Clock, lifecycle=Lifecycle.SINGLETON)
        .bind(EventLog, EventLog, lifecycle=Lifecycle.SINGLETON)
        .build()
    )
