# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Unit tests for :class:`tripack_runtime.Binding`."""

import asyncio
import dataclasses

import pytest

from tripack_contracts import BindingError, Lifecycle
from tripack_runtime import Binding


class _Clock:
    """Framework-neutral token target used across these tests."""


async def _async_clock_stub() -> _Clock:
    """Async factory stub shared by tests that need an ``async_factory``.

    Defined at module level (not inside each test) so a single
    invocation under :func:`asyncio.run` covers the body and the
    other tests can reference the stub without re-defining it.
    """
    return _Clock()


def test_construct_with_sync_factory() -> None:
    """A ``factory`` alone is a valid sync binding."""
    binding = Binding(token=_Clock, factory=_Clock)
    assert binding.token is _Clock
    assert binding.factory is _Clock
    assert binding.async_factory is None


def test_construct_with_async_factory() -> None:
    """An ``async_factory`` alone is a valid async binding."""
    binding = Binding(token=_Clock, async_factory=_async_clock_stub)
    assert binding.token is _Clock
    assert binding.factory is None
    assert binding.async_factory is _async_clock_stub


def test_async_clock_stub_returns_clock_instance() -> None:
    """Exercise the shared async factory stub once for coverage."""
    instance = asyncio.run(_async_clock_stub())
    assert isinstance(instance, _Clock)


def test_default_lifecycle_is_transient() -> None:
    """Bindings default to ``TRANSIENT`` when no lifecycle is given."""
    binding = Binding(token=_Clock, factory=_Clock)
    assert binding.lifecycle == Lifecycle.TRANSIENT


def test_default_auto_inject_is_false() -> None:
    """Bindings default to ``auto_inject=False`` (opt-in)."""
    binding = Binding(token=_Clock, factory=_Clock)
    assert binding.auto_inject is False


def test_explicit_lifecycle_and_auto_inject_are_stored() -> None:
    """Non-default field values round-trip into the binding."""
    binding = Binding(
        token=_Clock,
        factory=_Clock,
        lifecycle=Lifecycle.SINGLETON,
        auto_inject=True,
    )
    assert binding.lifecycle == Lifecycle.SINGLETON
    assert binding.auto_inject is True


def test_neither_factory_raises_binding_error() -> None:
    """Construction without any factory is rejected loudly."""
    with pytest.raises(BindingError, match="Exactly one of `factory`"):
        Binding(token=_Clock)


def test_both_factories_raise_binding_error() -> None:
    """Construction with both factories is rejected loudly."""
    with pytest.raises(BindingError, match="Exactly one of `factory`"):
        Binding(token=_Clock, factory=_Clock, async_factory=_async_clock_stub)


def test_binding_is_frozen() -> None:
    """Field assignment after construction raises :class:`FrozenInstanceError`.

    The write goes through a dynamic :func:`setattr` so neither mypy
    (frozen-write attribute warning) nor ruff (B010
    constant-attribute setattr) fire at static check time - the test
    asserts the *runtime* behaviour of frozen dataclasses.
    """
    binding = Binding(token=_Clock, factory=_Clock)
    target_attr = "factory"
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(binding, target_attr, _Clock)


def test_binding_uses_slots_not_dict() -> None:
    """``slots=True`` eliminates ``__dict__`` for memory efficiency."""
    binding = Binding(token=_Clock, factory=_Clock)
    assert not hasattr(binding, "__dict__")


def test_binding_is_hashable() -> None:
    """Frozen dataclasses are hashable by default, by all fields."""
    a = Binding(token=_Clock, factory=_Clock)
    b = Binding(token=_Clock, factory=_Clock)
    assert hash(a) == hash(b)
    assert {a, b} == {a}


def test_binding_equality_is_structural() -> None:
    """Two bindings with identical fields compare equal."""
    a = Binding(token=_Clock, factory=_Clock, lifecycle=Lifecycle.SINGLETON)
    b = Binding(token=_Clock, factory=_Clock, lifecycle=Lifecycle.SINGLETON)
    assert a == b


def test_binding_inequality_on_differing_fields() -> None:
    """Any differing field breaks equality."""
    base = Binding(token=_Clock, factory=_Clock)
    different_lifecycle = Binding(
        token=_Clock, factory=_Clock, lifecycle=Lifecycle.SCOPED
    )
    different_auto_inject = Binding(token=_Clock, factory=_Clock, auto_inject=True)
    assert base != different_lifecycle
    assert base != different_auto_inject


def test_dataclasses_replace_yields_new_instance() -> None:
    """``dataclasses.replace`` is the canonical "modify" pattern."""
    original = Binding(token=_Clock, factory=_Clock)
    promoted = dataclasses.replace(original, lifecycle=Lifecycle.SINGLETON)
    assert original.lifecycle == Lifecycle.TRANSIENT
    assert promoted.lifecycle == Lifecycle.SINGLETON
    assert original is not promoted


def test_binding_with_string_token() -> None:
    """A string token is a valid ``DependencyToken``."""
    binding = Binding(token="primary-clock", factory=_Clock)
    assert binding.token == "primary-clock"
    assert binding.factory is _Clock


def test_binding_with_tuple_token() -> None:
    """A composite tuple token is a valid ``DependencyToken``."""
    binding = Binding(token=("clock", "primary"), factory=_Clock)
    assert binding.token == ("clock", "primary")
