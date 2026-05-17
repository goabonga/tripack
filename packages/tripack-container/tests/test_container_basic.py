# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Unit tests for the container skeleton (4.1)."""

from __future__ import annotations

import asyncio

import pytest

from tripack_container import Container
from tripack_contracts import ResolutionError


class _Clock:
    """Framework-neutral token used as the canonical example."""


def test_container_can_be_instantiated_with_no_arguments() -> None:
    """The skeleton constructor takes no arguments and never raises."""
    Container()


def test_container_uses_slots_not_per_instance_dict() -> None:
    """``__slots__`` keeps the container instance small."""
    container = Container()
    assert not hasattr(container, "__dict__")


def test_resolve_on_an_empty_container_raises_resolution_error() -> None:
    """Without any binding, ``resolve`` surfaces :class:`ResolutionError`."""
    container = Container()
    with pytest.raises(ResolutionError, match="No binding registered"):
        container.resolve(_Clock)


async def _aresolve_empty() -> None:
    """Helper for the async-empty test: also raises :class:`ResolutionError`."""
    await Container().aresolve(_Clock)


def test_aresolve_on_an_empty_container_raises_resolution_error() -> None:
    """``aresolve`` propagates the same error as the sync path."""
    with pytest.raises(ResolutionError, match="No binding registered"):
        asyncio.run(_aresolve_empty())
