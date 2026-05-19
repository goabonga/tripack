# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Freeze the public API of :mod:`tripack_container`.

This module is the single source of truth for what
``tripack-container`` promises externally. The expected symbols
are listed in :data:`_EXPECTED_PUBLIC_API` and the test asserts
strict equality with ``tripack_container.__all__``; any
addition without updating the set fails CI - by design, so a
reviewer has to acknowledge new public surface explicitly.

Adding a new public symbol is a minor bump and follows the n+2
deprecation policy for any future removal. See
``docs/stability.md``.
"""

from typing import is_protocol

import tripack_container
from tripack_container import (
    Container,
    ContainerBuilder,
    Module,
    __version__,
    async_scoped,
    async_singleton,
    async_transient,
    inject,
    scoped,
    singleton,
    transient,
)

_EXPECTED_PUBLIC_API: frozenset[str] = frozenset(
    {
        # high-level API
        "Container",
        "ContainerBuilder",
        "Module",
        # provider helpers (sync + async pairs)
        "scoped",
        "singleton",
        "transient",
        "async_scoped",
        "async_singleton",
        "async_transient",
        # auto-injection marker (factory-level decorator)
        "inject",
        # call-site injection marker for Annotated[T, Inject]
        "Inject",
        # injection-plumbing error (no container reachable)
        "InjectionError",
        # version
        "__version__",
    }
)


def test_all_matches_expected_public_api_exactly() -> None:
    """``__all__`` equals the pinned expected set - no drift allowed."""
    actual = set(tripack_container.__all__)
    assert actual == _EXPECTED_PUBLIC_API, (
        f"Public API drift detected.\n"
        f"  Added:   {actual - _EXPECTED_PUBLIC_API}\n"
        f"  Removed: {_EXPECTED_PUBLIC_API - actual}"
    )


def test_all_is_sorted_alphabetically() -> None:
    """``__all__`` is kept in sorted order for diff stability."""
    assert list(tripack_container.__all__) == sorted(tripack_container.__all__)


def test_every_promised_symbol_is_importable() -> None:
    """Each entry in ``__all__`` resolves through the package."""
    for name in _EXPECTED_PUBLIC_API:
        assert hasattr(tripack_container, name), (
            f"`__all__` promises `{name}` but it is not exported."
        )


def test_no_underscored_internal_leaks_into_all() -> None:
    """``__all__`` contains no leading-underscore name (except dunders)."""
    for name in tripack_container.__all__:
        assert not (name.startswith("_") and not name.startswith("__")), (
            f"Private-by-convention name `{name}` leaked into __all__."
        )


def test_container_and_builder_use_slots() -> None:
    """The two stateful collaborators expose ``__slots__`` (no per-instance dict)."""
    assert hasattr(Container, "__slots__")
    assert hasattr(ContainerBuilder, "__slots__")
    container = Container()
    assert not hasattr(container, "__dict__")
    builder = ContainerBuilder()
    assert not hasattr(builder, "__dict__")


def test_module_is_a_protocol() -> None:
    """:class:`Module` is recognised by :func:`typing.is_protocol`."""
    assert is_protocol(Module)


def test_provider_helpers_are_callables() -> None:
    """The six provider helpers are exposed as callables."""
    assert callable(transient)
    assert callable(singleton)
    assert callable(scoped)
    assert callable(async_transient)
    assert callable(async_singleton)
    assert callable(async_scoped)


def test_inject_is_a_callable_decorator() -> None:
    """``inject`` is the standalone marker decorator."""
    assert callable(inject)


def test_container_exposes_the_documented_methods() -> None:
    """The container surface stays exactly as documented across the docs site.

    Uses ``getattr`` rather than ``inspect.getattr_static`` so
    classmethods (``from_toml`` / ``from_json`` / ``from_yaml``)
    appear bound and ``callable`` returns ``True`` on them.
    """
    expected_methods = {
        "bind",
        "bind_class",
        "resolve",
        "aresolve",
        "scope",
        "ascope",
        "close",
        "aclose",
        "from_toml",
        "from_json",
        "from_yaml",
    }
    actual_methods = {
        name
        for name in dir(Container)
        if not name.startswith("_") and callable(getattr(Container, name))
    }
    missing = expected_methods - actual_methods
    extra = actual_methods - expected_methods
    assert not missing and not extra, (
        f"Container method surface drift detected.\n"
        f"  Missing: {missing}\n"
        f"  Extra:   {extra}"
    )


def test_builder_exposes_the_documented_methods() -> None:
    """The builder surface stays exactly as documented across the docs site."""
    expected_methods = {"bind", "bind_class", "install", "build"}
    actual_methods = {
        name
        for name in dir(ContainerBuilder)
        if not name.startswith("_") and callable(getattr(ContainerBuilder, name))
    }
    missing = expected_methods - actual_methods
    extra = actual_methods - expected_methods
    assert not missing and not extra, (
        f"ContainerBuilder method surface drift detected.\n"
        f"  Missing: {missing}\n"
        f"  Extra:   {extra}"
    )


def test_version_is_a_non_empty_string() -> None:
    """``__version__`` is a non-empty string."""
    assert isinstance(__version__, str)
    assert __version__
