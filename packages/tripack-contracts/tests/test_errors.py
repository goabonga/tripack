# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Unit tests for the :mod:`tripack_contracts.errors` hierarchy."""

import pickle

import pytest

from tripack_contracts import (
    BindingError,
    CircularDependencyError,
    ConfigurationError,
    ResolutionError,
    ScopeError,
    TripackError,
)


def test_tripack_error_is_an_exception() -> None:
    """The root inherits from :class:`Exception`."""
    assert issubclass(TripackError, Exception)


def test_resolution_error_subclasses_tripack_error() -> None:
    assert issubclass(ResolutionError, TripackError)


def test_binding_error_subclasses_tripack_error() -> None:
    assert issubclass(BindingError, TripackError)


def test_scope_error_subclasses_tripack_error() -> None:
    assert issubclass(ScopeError, TripackError)


def test_configuration_error_subclasses_tripack_error() -> None:
    assert issubclass(ConfigurationError, TripackError)


def test_circular_dependency_error_subclasses_resolution_error() -> None:
    """The cycle case is a specialised :class:`ResolutionError`."""
    assert issubclass(CircularDependencyError, ResolutionError)


def test_every_error_can_be_raised_and_caught_as_tripack_error() -> None:
    """A single ``except TripackError`` catches every framework error."""
    for cls in (
        ResolutionError,
        BindingError,
        ScopeError,
        ConfigurationError,
    ):
        with pytest.raises(TripackError):
            raise cls("boom")


def test_tripack_error_can_be_raised_directly() -> None:
    """The root is concrete (no ABC enforcement) but discouraged."""
    with pytest.raises(TripackError, match="oops"):
        raise TripackError("oops")


def test_circular_dependency_error_stores_cycle_as_tuple() -> None:
    """The ``cycle`` attribute is the input frozen into a tuple."""

    class A:
        pass

    class B:
        pass

    err = CircularDependencyError([A, B, A])
    assert err.cycle == (A, B, A)


def test_circular_dependency_error_formats_classes_via_qualname() -> None:
    """Class tokens render as ``__qualname__`` in the message."""

    class Clock:
        pass

    class Cache:
        pass

    err = CircularDependencyError([Clock, Cache, Clock])
    assert "Circular dependency detected:" in str(err)
    assert "Clock" in str(err)
    assert "Cache" in str(err)
    assert " -> " in str(err)


def test_circular_dependency_error_formats_strings_via_repr() -> None:
    """Non-class tokens fall back to :func:`repr`."""
    err = CircularDependencyError(["primary-clock", "fallback-clock"])
    message = str(err)
    assert "'primary-clock'" in message
    assert "'fallback-clock'" in message


def test_circular_dependency_error_is_catchable_as_resolution_error() -> None:
    """The cycle case satisfies the broader ``ResolutionError`` clause."""

    class Token:
        pass

    with pytest.raises(ResolutionError):
        raise CircularDependencyError([Token, Token])


def test_circular_dependency_error_is_picklable() -> None:
    """Round-tripping through :mod:`pickle` preserves the cycle.

    The custom ``__reduce__`` ensures the ``cycle`` attribute is
    restored on the unpickled instance, not just the exception args.
    """
    err = CircularDependencyError(["a", "b", "a"])
    revived = pickle.loads(pickle.dumps(err))
    assert isinstance(revived, CircularDependencyError)
    assert revived.cycle == ("a", "b", "a")
    assert str(revived) == str(err)


def test_simple_subclasses_are_picklable() -> None:
    """Default ``Exception.__reduce__`` works for the plain subclasses."""
    for cls in (
        TripackError,
        ResolutionError,
        BindingError,
        ScopeError,
        ConfigurationError,
    ):
        err = cls("boom")
        revived = pickle.loads(pickle.dumps(err))
        assert isinstance(revived, cls)
        assert revived.args == ("boom",)
