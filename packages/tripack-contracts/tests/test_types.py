# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Unit tests for :data:`tripack_contracts.DependencyToken`."""

from typing import TypeAliasType

from tripack_contracts import DependencyToken


def test_dependency_token_is_a_type_alias_type() -> None:
    """The exported name is a PEP 695 :class:`TypeAliasType`."""
    assert isinstance(DependencyToken, TypeAliasType)


def test_dependency_token_exposes_its_declared_name() -> None:
    """The alias carries its declared name for tooling and traces."""
    assert DependencyToken.__name__ == "DependencyToken"


def test_class_satisfies_dependency_token() -> None:
    """A class is a valid token - the canonical case."""

    class Clock:
        """Framework-neutral token target used by tests."""

    token: DependencyToken = Clock
    assert token is Clock


def test_string_satisfies_dependency_token() -> None:
    """A plain string is a valid token - named binding pattern."""
    token: DependencyToken = "primary-clock"
    assert token == "primary-clock"


def test_hashable_value_satisfies_dependency_token() -> None:
    """An arbitrary hashable value is accepted - composite token."""
    token: DependencyToken = ("clock", "primary")
    assert token == ("clock", "primary")


def test_dependency_token_repr_is_stable() -> None:
    """``repr(DependencyToken)`` returns the alias name, not the union."""
    assert repr(DependencyToken) == "DependencyToken"
