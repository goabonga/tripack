# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Unit tests for the :class:`Module` protocol and ``install`` idempotence (4.4)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tripack_container import ContainerBuilder, Module
from tripack_contracts import BindingError, Lifecycle

if TYPE_CHECKING:
    from tripack_container.builder import ContainerBuilder as _Builder


class _Clock:
    """Framework-neutral token used across these tests."""


class _Cache:
    """A second token used to verify multi-binding modules."""


class _Logger:
    """A third token used to verify module composition."""


def _make_clock() -> _Clock:
    """Module-level sync factory: returns a fresh :class:`_Clock`."""
    return _Clock()


def _make_cache() -> _Cache:
    """Module-level sync factory: returns a fresh :class:`_Cache`."""
    return _Cache()


def _make_logger() -> _Logger:
    """Module-level sync factory: returns a fresh :class:`_Logger`."""
    return _Logger()


def _other_make_clock() -> _Clock:
    """Competing sync factory used by :class:`_ConflictingClockModule`.

    Extracted to the module level so its body is exercised
    independently of the conflict test - the bind in
    :class:`_ConflictingClockModule.register` raises before
    the factory can run, so a nested-function form would be
    dead code.
    """
    return _Clock()


class _ClockModule:
    """Test stand-in that registers a single Clock binding."""

    def __init__(self) -> None:
        """Track register-invocation count for the idempotence test."""
        self.register_calls = 0

    def register(self, builder: _Builder) -> None:
        """Bind ``_Clock`` to ``_make_clock`` and bump the call counter."""
        self.register_calls += 1
        builder.bind(_Clock, _make_clock)


class _CompositeModule:
    """Module that installs sub-modules and adds its own bindings."""

    def __init__(self) -> None:
        """Initialise without state - the test installs a fresh instance."""

    def register(self, builder: _Builder) -> None:
        """Install :class:`_ClockModule` first, then bind ``_Cache``."""
        builder.install(_ClockModule())
        builder.bind(_Cache, _make_cache)


class _ConflictingClockModule:
    """Module that binds ``_Clock`` to a different factory.

    Used to verify conflict detection between two modules
    that both claim the same token with incompatible
    factories.
    """

    def register(self, builder: _Builder) -> None:
        """Bind ``_Clock`` to a competing factory."""
        builder.bind(_Clock, _other_make_clock)


def test_module_protocol_satisfies_typing_structural_check() -> None:
    """A class with the right ``register`` shape is a ``Module`` for typing."""
    # mypy strict will accept this annotation; the runtime assertion
    # keeps the test live without requiring runtime_checkable.
    module: Module = _ClockModule()
    assert callable(module.register)


def test_install_applies_module_bindings_to_the_builder() -> None:
    """After ``install``, the bound token is resolvable through the container."""
    container = ContainerBuilder().install(_ClockModule()).build()
    assert isinstance(container.resolve(_Clock), _Clock)


def test_install_returns_self_for_fluent_chaining() -> None:
    """``install`` mirrors ``bind`` and returns the builder itself."""
    builder = ContainerBuilder()
    same = builder.install(_ClockModule())
    assert same is builder


def test_install_called_twice_on_the_same_instance_is_a_noop() -> None:
    """A second ``install`` of the same module instance does not re-register."""
    module = _ClockModule()
    ContainerBuilder().install(module).install(module).build()
    # register() ran exactly once: the second install bailed out at the
    # per-instance guard, before reaching the bind site.
    assert module.register_calls == 1


def test_install_runs_two_distinct_instances_of_the_same_module_class() -> None:
    """Two separate instances are tracked separately and both run.

    The graph's idempotent register then deduplicates the
    actual bindings if they happen to be structurally
    identical.
    """
    first = _ClockModule()
    second = _ClockModule()
    builder = ContainerBuilder().install(first).install(second)
    assert first.register_calls == 1
    assert second.register_calls == 1
    # The two registers produced identical bindings; the
    # container still resolves cleanly thanks to the graph's
    # idempotence.
    container = builder.build()
    assert isinstance(container.resolve(_Clock), _Clock)


def test_install_supports_module_composition_via_recursive_install() -> None:
    """A module's ``register`` can install sub-modules."""
    container = ContainerBuilder().install(_CompositeModule()).build()
    assert isinstance(container.resolve(_Clock), _Clock)
    assert isinstance(container.resolve(_Cache), _Cache)


def test_install_detects_conflicting_bindings_across_modules() -> None:
    """Two modules binding the same token differently raises BindingError.

    Smoke-invokes the competing factory before the conflict
    attempt so its body stays covered: the install raises
    before any resolution, so the factory would otherwise be
    dead code in this test.
    """
    assert isinstance(_other_make_clock(), _Clock)
    builder = ContainerBuilder().install(_ClockModule())
    with pytest.raises(BindingError, match="Conflicting binding"):
        builder.install(_ConflictingClockModule())


def test_install_supports_mixing_with_bind_chains() -> None:
    """``install`` and ``bind`` interleave naturally in fluent chains."""
    container = (
        ContainerBuilder()
        .install(_ClockModule())
        .bind(_Logger, _make_logger, lifecycle=Lifecycle.SINGLETON)
        .install(_CompositeModule())
        .build()
    )
    assert isinstance(container.resolve(_Clock), _Clock)
    assert isinstance(container.resolve(_Cache), _Cache)
    assert isinstance(container.resolve(_Logger), _Logger)
