# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Freeze the public API of :mod:`tripack_contracts`.

This module is the single source of truth for what
``tripack-contracts`` promises externally:

- The expected symbols are listed in
  :data:`_EXPECTED_PUBLIC_API` and the test asserts strict equality
  with ``tripack_contracts.__all__``. Any addition without updating
  this set fails CI - which is by design, the test forces a code
  reviewer to acknowledge new public surface explicitly.
- Each promised symbol is also import-checked, so a renamed module
  that breaks an export reaches the test before reaching the
  consumer.
- The types of the foundational symbols are pinned (Protocol /
  TypedDict / Exception / enum / module) so an accidental class
  re-parenting cannot slip through silently.

Adding a new public symbol is a minor bump and follows the n+2
policy for any future removal. See ``docs/stability.md``.
"""

from enum import StrEnum
from typing import is_protocol, is_typeddict

import tripack_contracts
from tripack_contracts import (
    AsyncCloseable,
    AsyncProvider,
    AsyncResolver,
    BindingError,
    BindingSpec,
    CircularDependencyError,
    Closeable,
    ConfigurationError,
    ContainerConfig,
    DependencyToken,
    Lifecycle,
    Provider,
    ResolutionError,
    Resolver,
    ScopeError,
    TripackError,
    __version__,
)

_EXPECTED_PUBLIC_API: frozenset[str] = frozenset(
    {
        # protocols (sync + async pairs)
        "AsyncCloseable",
        "AsyncProvider",
        "AsyncResolver",
        "Closeable",
        "Provider",
        "Resolver",
        # data types
        "BindingSpec",
        "ContainerConfig",
        "DependencyToken",
        "Lifecycle",
        # exceptions
        "BindingError",
        "CircularDependencyError",
        "ConfigurationError",
        "ResolutionError",
        "ScopeError",
        "TripackError",
        # version
        "__version__",
    }
)


def test_all_matches_expected_public_api_exactly() -> None:
    """``__all__`` equals the pinned expected set - no drift allowed."""
    actual = set(tripack_contracts.__all__)
    assert actual == _EXPECTED_PUBLIC_API, (
        f"Public API drift detected.\n"
        f"  Added:   {actual - _EXPECTED_PUBLIC_API}\n"
        f"  Removed: {_EXPECTED_PUBLIC_API - actual}"
    )


def test_all_is_sorted_alphabetically() -> None:
    """``__all__`` is kept in sorted order for diff stability."""
    assert list(tripack_contracts.__all__) == sorted(tripack_contracts.__all__)


def test_every_promised_symbol_is_importable() -> None:
    """Each entry in ``__all__`` resolves through the package."""
    for name in _EXPECTED_PUBLIC_API:
        assert hasattr(tripack_contracts, name), (
            f"`__all__` promises `{name}` but it is not exported."
        )


def test_no_underscored_internal_leaks_into_all() -> None:
    """``__all__`` contains no leading-underscore name (except dunders)."""
    for name in tripack_contracts.__all__:
        assert not (name.startswith("_") and not name.startswith("__")), (
            f"Private-by-convention name `{name}` leaked into __all__."
        )


def test_protocols_are_protocols() -> None:
    """The six protocol classes are recognised by :func:`typing.is_protocol`."""
    for proto in (
        Closeable,
        AsyncCloseable,
        Provider,
        AsyncProvider,
        Resolver,
        AsyncResolver,
    ):
        assert is_protocol(proto), f"{proto.__name__} should be a Protocol"


def test_typed_dicts_are_typed_dicts() -> None:
    """The two TypedDict classes are recognised by :func:`typing.is_typeddict`."""
    assert is_typeddict(BindingSpec)
    assert is_typeddict(ContainerConfig)


def test_lifecycle_is_a_str_enum() -> None:
    """:class:`Lifecycle` inherits from :class:`StrEnum`."""
    assert issubclass(Lifecycle, StrEnum)


def test_exception_hierarchy_is_pinned() -> None:
    """The exception tree shape is part of the public API."""
    assert issubclass(ResolutionError, TripackError)
    assert issubclass(BindingError, TripackError)
    assert issubclass(ScopeError, TripackError)
    assert issubclass(ConfigurationError, TripackError)
    assert issubclass(CircularDependencyError, ResolutionError)
    assert issubclass(TripackError, Exception)


def test_dependency_token_is_a_type_alias() -> None:
    """:data:`DependencyToken` is a PEP 695 :class:`TypeAliasType`."""
    from typing import TypeAliasType

    assert isinstance(DependencyToken, TypeAliasType)


def test_version_is_a_string() -> None:
    """``__version__`` is a non-empty string."""
    assert isinstance(__version__, str)
    assert __version__
