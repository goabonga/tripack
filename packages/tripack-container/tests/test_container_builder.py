# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Unit tests for :class:`ContainerBuilder` (4.3)."""

from __future__ import annotations

import pytest

from tripack_container import Container, ContainerBuilder
from tripack_contracts import BindingError, Lifecycle


class _Clock:
    """Framework-neutral token for these tests."""


class _Cache:
    """A second token, used to verify multi-bind chaining."""


def _make_clock() -> _Clock:
    """Module-level sync factory: returns a fresh :class:`_Clock`."""
    return _Clock()


def _make_cache() -> _Cache:
    """Module-level sync factory: returns a fresh :class:`_Cache`."""
    return _Cache()


def test_builder_bind_returns_self_for_chaining() -> None:
    """``bind`` returns the builder itself, enabling fluent chaining."""
    builder = ContainerBuilder()
    same = builder.bind(_Clock, _make_clock)
    assert same is builder


def test_builder_build_returns_a_container_with_the_registered_bindings() -> None:
    """``build`` materialises the bindings into a working container."""
    container = ContainerBuilder().bind(_Clock, _make_clock).build()
    assert isinstance(container, Container)
    assert isinstance(container.resolve(_Clock), _Clock)


def test_builder_supports_multi_bind_chains() -> None:
    """Successive ``bind`` calls accumulate into one container."""
    container = (
        ContainerBuilder().bind(_Clock, _make_clock).bind(_Cache, _make_cache).build()
    )
    assert isinstance(container.resolve(_Clock), _Clock)
    assert isinstance(container.resolve(_Cache), _Cache)


def test_built_container_is_sealed_against_further_binds() -> None:
    """``Container.bind`` raises BindingError after build."""
    container = ContainerBuilder().bind(_Clock, _make_clock).build()
    with pytest.raises(BindingError, match="Container is sealed"):
        container.bind(_Cache, _make_cache)


def test_builder_build_called_twice_produces_independent_containers() -> None:
    """Two builds from the same builder share bindings but not resolver state."""
    builder = ContainerBuilder().bind(
        _Clock, _make_clock, lifecycle=Lifecycle.SINGLETON
    )
    first = builder.build()
    second = builder.build()
    # Equivalent: each container resolves the token to a _Clock.
    assert isinstance(first.resolve(_Clock), _Clock)
    assert isinstance(second.resolve(_Clock), _Clock)
    # Independent: singletons cached in `first` are not visible from `second`.
    assert first.resolve(_Clock) is not second.resolve(_Clock)
    # And within one container, the singleton cache works as expected.
    assert first.resolve(_Clock) is first.resolve(_Clock)


def test_builder_bind_after_build_does_not_affect_already_built_containers() -> None:
    """The snapshot semantics isolate built containers from later builder mutations."""
    builder = ContainerBuilder().bind(_Clock, _make_clock)
    container = builder.build()
    # Add a new binding to the builder AFTER build.
    builder.bind(_Cache, _make_cache)
    # The already-built container does not see the new binding.
    with pytest.raises(Exception, match="No binding registered"):
        container.resolve(_Cache)
    # But a fresh build picks it up.
    fresh = builder.build()
    assert isinstance(fresh.resolve(_Cache), _Cache)


def test_builder_build_with_no_bindings_returns_an_empty_sealed_container() -> None:
    """``build`` works on an untouched builder; the container is still sealed."""
    container = ContainerBuilder().build()
    with pytest.raises(BindingError, match="Container is sealed"):
        container.bind(_Clock, _make_clock)


def test_seal_is_idempotent_on_a_container_already_sealed() -> None:
    """Calling the internal ``_seal`` twice does not toggle anything."""
    container = ContainerBuilder().bind(_Clock, _make_clock).build()
    container._seal()  # second seal is a no-op
    with pytest.raises(BindingError, match="Container is sealed"):
        container.bind(_Cache, _make_cache)


def test_builder_uses_slots_not_per_instance_dict() -> None:
    """``__slots__`` keeps builder instances small."""
    builder = ContainerBuilder()
    assert not hasattr(builder, "__dict__")


def test_unfrozen_container_still_accepts_direct_bind_calls() -> None:
    """The default :class:`Container` constructor is unfrozen."""
    container = Container()
    container.bind(_Clock, _make_clock)
    assert isinstance(container.resolve(_Clock), _Clock)
