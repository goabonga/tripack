# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""End-to-end idempotent registration through the public Container API."""

from __future__ import annotations

import _fixtures as F
import pytest

from tripack_container import Container, ContainerBuilder
from tripack_contracts import BindingError, Lifecycle


def test_rebind_identical_factory_and_lifecycle_is_a_noop() -> None:
    """Re-binding the same ``(token, factory, lifecycle)`` tuple does not raise."""
    container = Container()
    container.bind(F.Clock, F.make_clock, lifecycle=Lifecycle.SINGLETON)
    container.bind(F.Clock, F.make_clock, lifecycle=Lifecycle.SINGLETON)
    # The idempotent guard kept exactly one binding; the singleton still works.
    assert container.resolve(F.Clock) is container.resolve(F.Clock)


def test_rebind_conflicting_factory_raises_binding_error() -> None:
    """A different factory for the same token surfaces ``BindingError``."""

    def _alt_make_clock() -> F.Clock:
        return F.Clock()

    container = Container()
    container.bind(F.Clock, F.make_clock)
    with pytest.raises(BindingError, match="Conflicting binding"):
        container.bind(F.Clock, _alt_make_clock)


def test_rebind_conflicting_lifecycle_raises_binding_error() -> None:
    """The same factory with a different lifecycle is also a conflict."""
    container = Container()
    container.bind(F.Clock, F.make_clock, lifecycle=Lifecycle.TRANSIENT)
    with pytest.raises(BindingError, match="Conflicting binding"):
        container.bind(F.Clock, F.make_clock, lifecycle=Lifecycle.SINGLETON)


def test_module_idempotence_combines_with_direct_bind_safely() -> None:
    """Installing a Module then re-binding one of its tokens raises BindingError.

    The Module's :class:`Clock` binding is registered first; the
    subsequent direct ``bind`` with a different lifecycle raises
    cleanly via the same idempotent-guard path - the user is told
    at builder-time, not at resolve-time.
    """
    builder = ContainerBuilder().install(F.AppModule())
    with pytest.raises(BindingError, match="Conflicting binding"):
        builder.bind(F.Clock, F.make_clock, lifecycle=Lifecycle.TRANSIENT)
