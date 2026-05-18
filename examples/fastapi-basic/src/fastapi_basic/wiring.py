# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Container assembly for the FastAPI + Tripack example.

A single composition-root function: build a sealed
:class:`Container` from a fluent :class:`ContainerBuilder`
chain. The function is also the natural place for tests to
swap a binding (``with build_container(clock=FakeClock()):``
in a real app); this example keeps it parameter-free for
brevity.
"""

from fastapi_basic.services import Clock, EventLog, RequestId
from tripack_container import Container, ContainerBuilder
from tripack_contracts import Lifecycle


def build_container() -> Container:
    """Return a sealed :class:`Container` wired for the demo service.

    Three bindings:

    - :class:`Clock`     - ``SINGLETON``: one wall-clock for the process.
    - :class:`RequestId` - ``SCOPED``  : one identifier per HTTP request.
    - :class:`EventLog`  - ``SINGLETON``: shared event store.

    The middleware in :mod:`fastapi_basic.api` opens a
    :class:`Scope` per request, so the SCOPED binding above
    has a place to cache its instance.
    """
    return (
        ContainerBuilder()
        .bind(Clock, Clock, lifecycle=Lifecycle.SINGLETON)
        .bind(RequestId, RequestId, lifecycle=Lifecycle.SCOPED)
        .bind(EventLog, EventLog, lifecycle=Lifecycle.SINGLETON)
        .build()
    )
