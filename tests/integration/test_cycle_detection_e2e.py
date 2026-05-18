# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""End-to-end cycle detection through the public Container API."""

from __future__ import annotations

from typing import Any

import pytest

from tripack_container import Container
from tripack_contracts import CircularDependencyError


class _Reader:
    """Service that depends on a Writer via factory recursion."""


class _Writer:
    """Service that depends on a Reader via factory recursion."""


def test_two_step_factory_cycle_surfaces_as_circular_dependency_error() -> None:
    """Reader -> Writer -> Reader is detected and named in the cycle attribute."""
    container = Container()
    resolver_ref: Container = container

    def _make_reader() -> Any:
        resolver_ref.resolve(_Writer)

    def _make_writer() -> Any:
        resolver_ref.resolve(_Reader)

    container.bind(_Reader, _make_reader)
    container.bind(_Writer, _make_writer)

    with pytest.raises(CircularDependencyError) as exc_info:
        container.resolve(_Reader)
    assert exc_info.value.cycle == (_Reader, _Writer, _Reader)


def test_self_referential_factory_surfaces_as_circular_dependency_error() -> None:
    """A factory that resolves its own token immediately raises a 1-step cycle."""
    container = Container()
    resolver_ref: Container = container

    def _make() -> Any:
        resolver_ref.resolve(_Reader)

    container.bind(_Reader, _make)

    with pytest.raises(CircularDependencyError) as exc_info:
        container.resolve(_Reader)
    assert exc_info.value.cycle == (_Reader, _Reader)
