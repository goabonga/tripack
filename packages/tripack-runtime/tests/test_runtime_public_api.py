# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Freeze the public API of :mod:`tripack_runtime`.

This module is the single source of truth for what
``tripack-runtime`` promises externally:

- The expected symbols are listed in
  :data:`_EXPECTED_PUBLIC_API` and the test asserts strict
  equality with ``tripack_runtime.__all__``. Any addition
  without updating this set fails CI - which is by design, the
  test forces a reviewer to acknowledge new public surface
  explicitly.
- Each promised symbol is also import-checked, so a renamed
  module that breaks an export reaches the test before reaching
  the consumer.
- The kinds of the foundational symbols are pinned (dataclass
  shape, class type, callable, version) so an accidental
  refactor cannot silently change the surface.

Adding a new public symbol is a minor bump and follows the n+2
deprecation policy for any future removal. See
``docs/stability.md``.
"""

import dataclasses
import inspect

import pytest

import tripack_runtime
from tripack_runtime import (
    Binding,
    DependencyGraph,
    ResolutionContext,
    Resolver,
    Scope,
    __version__,
    aguarded_resolving,
    alifetime_scope,
    aresolution_scope,
    check_for_cycle,
    current_context,
    current_scope,
    guarded_resolving,
    lifetime_scope,
    resolution_scope,
)

_EXPECTED_PUBLIC_API: frozenset[str] = frozenset(
    {
        # data types
        "Binding",
        # collaborators
        "DependencyGraph",
        "ResolutionContext",
        "Resolver",
        "Scope",
        # cycle detection
        "aguarded_resolving",
        "check_for_cycle",
        "guarded_resolving",
        # context managers
        "alifetime_scope",
        "aresolution_scope",
        "current_context",
        "current_scope",
        "lifetime_scope",
        "resolution_scope",
        # version
        "__version__",
    }
)


def test_all_matches_expected_public_api_exactly() -> None:
    """``__all__`` equals the pinned expected set - no drift allowed."""
    actual = set(tripack_runtime.__all__)
    assert actual == _EXPECTED_PUBLIC_API, (
        f"Public API drift detected.\n"
        f"  Added:   {actual - _EXPECTED_PUBLIC_API}\n"
        f"  Removed: {_EXPECTED_PUBLIC_API - actual}"
    )


def test_all_is_sorted_alphabetically() -> None:
    """``__all__`` is kept in sorted order for diff stability."""
    assert list(tripack_runtime.__all__) == sorted(tripack_runtime.__all__)


def test_every_promised_symbol_is_importable() -> None:
    """Each entry in ``__all__`` resolves through the package."""
    for name in _EXPECTED_PUBLIC_API:
        assert hasattr(tripack_runtime, name), (
            f"`__all__` promises `{name}` but it is not exported."
        )


def test_no_underscored_internal_leaks_into_all() -> None:
    """``__all__`` contains no leading-underscore name (except dunders)."""
    for name in tripack_runtime.__all__:
        assert not (name.startswith("_") and not name.startswith("__")), (
            f"Private-by-convention name `{name}` leaked into __all__."
        )


def test_binding_is_a_frozen_slotted_dataclass() -> None:
    """``Binding`` is a frozen, slotted dataclass (immutable value type).

    The frozen check is behavioural: attempting to mutate a
    field raises :class:`dataclasses.FrozenInstanceError`,
    which is the contract consumers rely on. Avoiding a direct
    read of the private ``__dataclass_params__`` keeps mypy
    quiet without an escape hatch.
    """
    assert dataclasses.is_dataclass(Binding)
    # slots=True produces a __slots__ attribute on the class.
    assert hasattr(Binding, "__slots__")
    instance = Binding(token=object, factory=lambda: None)
    # And no per-instance __dict__ (the slots guarantee).
    assert not hasattr(instance, "__dict__")
    # Frozen: re-assignment raises FrozenInstanceError. Variable
    # attribute name bypasses ruff B010 (constant setattr) without
    # needing a type-ignore - direct ``instance.token = int`` would
    # also be caught by mypy.
    target_attr = "token"
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(instance, target_attr, int)


def test_collaborators_are_classes() -> None:
    """The runtime collaborators are concrete classes (not aliases or factories)."""
    for cls in (DependencyGraph, ResolutionContext, Resolver, Scope):
        assert inspect.isclass(cls), f"{cls!r} should be a class"


def test_collaborators_use_slots_not_per_instance_dict() -> None:
    """Each collaborator uses ``__slots__`` to keep instances small.

    The slots guarantee is part of the contract: tooling and
    subclasses can rely on the absence of ``__dict__``.
    """
    assert hasattr(DependencyGraph, "__slots__")
    assert hasattr(ResolutionContext, "__slots__")
    assert hasattr(Resolver, "__slots__")
    assert hasattr(Scope, "__slots__")


def test_cycle_detection_helpers_are_callable() -> None:
    """The three cycle-detection helpers are exposed as callables."""
    assert callable(check_for_cycle)
    assert callable(guarded_resolving)
    assert callable(aguarded_resolving)


def test_context_manager_helpers_are_callable() -> None:
    """All scope / context entry points are exposed as callables."""
    assert callable(resolution_scope)
    assert callable(aresolution_scope)
    assert callable(lifetime_scope)
    assert callable(alifetime_scope)
    assert callable(current_context)
    assert callable(current_scope)


def test_version_is_a_non_empty_string() -> None:
    """``__version__`` is a non-empty string."""
    assert isinstance(__version__, str)
    assert __version__
