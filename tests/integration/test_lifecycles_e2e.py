# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""End-to-end tests for the three lifecycles via the public Container API."""

from __future__ import annotations

import _fixtures as F

from tripack_container import ContainerBuilder
from tripack_contracts import Lifecycle


def test_transient_lifecycle_yields_fresh_instance_per_resolve() -> None:
    """TRANSIENT bindings never cache; each ``resolve`` builds anew."""
    container = (
        ContainerBuilder()
        .bind(F.Clock, F.make_clock, lifecycle=Lifecycle.TRANSIENT)
        .build()
    )
    assert container.resolve(F.Clock) is not container.resolve(F.Clock)


def test_singleton_lifecycle_shares_one_instance_across_scopes() -> None:
    """SINGLETON instances survive scope boundaries: same identity everywhere."""
    container = (
        ContainerBuilder()
        .bind(F.Clock, F.make_clock, lifecycle=Lifecycle.SINGLETON)
        .build()
    )
    bare = container.resolve(F.Clock)
    with container.scope():
        in_scope = container.resolve(F.Clock)
    with container.scope():
        in_another_scope = container.resolve(F.Clock)
    assert bare is in_scope
    assert in_scope is in_another_scope


def test_scoped_lifecycle_produces_distinct_instances_across_scopes() -> None:
    """SCOPED bindings cache per-scope; different scopes hold different instances."""
    container = (
        ContainerBuilder()
        .bind(F.Session, F.make_session, lifecycle=Lifecycle.SCOPED)
        .build()
    )
    with container.scope():
        first_within = container.resolve(F.Session)
        second_within = container.resolve(F.Session)
    with container.scope():
        in_other_scope = container.resolve(F.Session)
    assert first_within is second_within
    assert first_within is not in_other_scope


def test_scope_exit_runs_teardown_on_scoped_closeables() -> None:
    """A SCOPED Closeable is torn down on scope exit, not earlier."""
    container = (
        ContainerBuilder()
        .bind(F.Session, F.make_session, lifecycle=Lifecycle.SCOPED)
        .build()
    )
    with container.scope():
        session = container.resolve(F.Session)
        assert session.close_calls == 0
    # Scope exited; close() ran once via the auto-close machinery.
    assert session.close_calls == 1


def test_container_exit_runs_teardown_on_singleton_closeables() -> None:
    """A SINGLETON Closeable is torn down when the container is closed."""
    with (
        ContainerBuilder()
        .bind(F.Pool, F.make_pool, lifecycle=Lifecycle.SINGLETON)
        .build() as container
    ):
        pool = container.resolve(F.Pool)
        assert pool.close_calls == 0
    # Container exited; close() ran once.
    assert pool.close_calls == 1


def test_singleton_and_scoped_close_with_lifo_ordering() -> None:
    """Container-level teardown closes the SINGLETONs after scope teardown ran."""
    order: list[str] = []

    class FirstPool:
        """First SINGLETON, records 'pool-first' on close."""

        def close(self) -> None:
            order.append("pool-first")

    class SecondPool:
        """Second SINGLETON, records 'pool-second' on close."""

        def close(self) -> None:
            order.append("pool-second")

    class ScopedThing:
        """SCOPED resource, records 'scoped' on close."""

        def close(self) -> None:
            order.append("scoped")

    with (
        ContainerBuilder()
        .bind(FirstPool, FirstPool, lifecycle=Lifecycle.SINGLETON)
        .bind(SecondPool, SecondPool, lifecycle=Lifecycle.SINGLETON)
        .bind(ScopedThing, ScopedThing, lifecycle=Lifecycle.SCOPED)
        .build()
    ) as container:
        container.resolve(FirstPool)
        container.resolve(SecondPool)
        with container.scope():
            container.resolve(ScopedThing)
    # Scope exit: scoped first. Container exit: SINGLETONs in LIFO.
    assert order == ["scoped", "pool-second", "pool-first"]
