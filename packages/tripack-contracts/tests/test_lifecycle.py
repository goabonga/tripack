# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Unit tests for :class:`tripack_contracts.Lifecycle`."""

from enum import StrEnum

import pytest

from tripack_contracts import Lifecycle


def test_lifecycle_is_a_str_enum() -> None:
    """The class inherits from :class:`enum.StrEnum`."""
    assert issubclass(Lifecycle, StrEnum)


def test_transient_value() -> None:
    """``TRANSIENT`` carries the string ``"transient"``."""
    assert Lifecycle.TRANSIENT.value == "transient"


def test_singleton_value() -> None:
    """``SINGLETON`` carries the string ``"singleton"``."""
    assert Lifecycle.SINGLETON.value == "singleton"


def test_scoped_value() -> None:
    """``SCOPED`` carries the string ``"scoped"``."""
    assert Lifecycle.SCOPED.value == "scoped"


def test_str_enum_equality_contract() -> None:
    """Members compare equal to their string value (StrEnum invariant).

    Variables are typed as :class:`str` to bypass the mypy
    ``comparison-overlap`` false-positive that fires on
    ``Lifecycle.TRANSIENT == "transient"`` (mypy sees two
    non-overlapping ``Literal`` types). The runtime contract is
    exercised through the wider :class:`str` annotation.
    """
    transient: str = Lifecycle.TRANSIENT
    singleton: str = Lifecycle.SINGLETON
    scoped: str = Lifecycle.SCOPED
    assert transient == "transient"
    assert singleton == "singleton"
    assert scoped == "scoped"


def test_members_iterate_in_declaration_order() -> None:
    """Iterating yields exactly the three members in source order."""
    assert list(Lifecycle) == [
        Lifecycle.TRANSIENT,
        Lifecycle.SINGLETON,
        Lifecycle.SCOPED,
    ]


def test_construction_from_value() -> None:
    """``Lifecycle("...")`` returns the matching member (idempotent)."""
    assert Lifecycle("transient") is Lifecycle.TRANSIENT
    assert Lifecycle("singleton") is Lifecycle.SINGLETON
    assert Lifecycle("scoped") is Lifecycle.SCOPED


def test_construction_from_unknown_value_raises_value_error() -> None:
    """Unknown values raise :class:`ValueError`, not return a default."""
    with pytest.raises(ValueError, match="'permanent'"):
        Lifecycle("permanent")


def test_member_is_string_instance() -> None:
    """Each member is a real :class:`str` (StrEnum invariant)."""
    for member in Lifecycle:
        assert isinstance(member, str)


def test_member_str_equals_value() -> None:
    """``str(member)`` returns the bare value, not the enum repr."""
    assert str(Lifecycle.TRANSIENT) == "transient"
    assert str(Lifecycle.SINGLETON) == "singleton"
    assert str(Lifecycle.SCOPED) == "scoped"
