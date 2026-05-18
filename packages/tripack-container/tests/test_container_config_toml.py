# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Unit tests for :meth:`Container.from_toml` (4.9)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import _config_fixtures as fixtures
import pytest

from tripack_container import Container
from tripack_contracts import ConfigurationError

# The loaders resolve tokens / factories via dotted Python names;
# tests reference the importable ``fixtures`` module so the loader
# can locate the actual objects through ``importlib.import_module``.
_FIXTURES = fixtures.__name__


def test_from_toml_loads_a_simple_singleton_binding(tmp_path: Path) -> None:
    """A minimal TOML config produces a working SINGLETON binding."""
    config = tmp_path / "config.toml"
    config.write_text(
        f"""
[[bindings]]
token = "{_FIXTURES}.FixtureClock"
factory = "{_FIXTURES}.make_clock"
lifecycle = "singleton"
"""
    )
    container = Container.from_toml(config)
    first = container.resolve(fixtures.FixtureClock)
    second = container.resolve(fixtures.FixtureClock)
    assert isinstance(first, fixtures.FixtureClock)
    assert first is second  # SINGLETON cached


def test_from_toml_loads_multiple_bindings_in_one_file(tmp_path: Path) -> None:
    """Multiple ``[[bindings]]`` entries each register on the container."""
    config = tmp_path / "config.toml"
    config.write_text(
        f"""
[[bindings]]
token = "{_FIXTURES}.FixtureClock"
factory = "{_FIXTURES}.make_clock"
lifecycle = "transient"

[[bindings]]
token = "{_FIXTURES}.FixtureCache"
factory = "{_FIXTURES}.make_cache"
lifecycle = "singleton"
"""
    )
    container = Container.from_toml(config)
    assert isinstance(container.resolve(fixtures.FixtureClock), fixtures.FixtureClock)
    assert isinstance(container.resolve(fixtures.FixtureCache), fixtures.FixtureCache)


async def _aresolve_async_binding(config: Path) -> fixtures.FixtureClock:
    """Coroutine helper: load + aresolve an async factory binding."""
    container = Container.from_toml(config)
    return await container.aresolve(fixtures.FixtureClock)


def test_from_toml_supports_async_factories(tmp_path: Path) -> None:
    """An async factory registered via TOML resolves through ``aresolve``."""
    config = tmp_path / "config.toml"
    config.write_text(
        f"""
[[bindings]]
token = "{_FIXTURES}.FixtureClock"
factory = "{_FIXTURES}.make_clock_async"
lifecycle = "transient"
"""
    )
    instance = asyncio.run(_aresolve_async_binding(config))
    assert isinstance(instance, fixtures.FixtureClock)


def test_from_toml_installs_a_module(tmp_path: Path) -> None:
    """The ``modules`` array runs each module's ``register`` on build."""
    config = tmp_path / "config.toml"
    config.write_text(
        f"""
modules = ["{_FIXTURES}.FixtureModule"]
bindings = []
"""
    )
    container = Container.from_toml(config)
    assert isinstance(container.resolve(fixtures.FixtureCache), fixtures.FixtureCache)


# --- validation errors ----------------------------------------------------


def test_from_toml_rejects_a_top_level_array(tmp_path: Path) -> None:
    """A TOML file whose root is not a table (post-tomllib it would be a dict).

    tomllib always parses to a dict at the top level, so the only
    way to hit the "top-level must be a dict" branch from the
    validator is to call ``build_container_from_config`` with a
    non-dict directly - exercised below.
    """
    from tripack_container.loaders import build_container_from_config

    with pytest.raises(ConfigurationError, match="top level"):
        build_container_from_config([])


def test_from_toml_rejects_missing_bindings_key(tmp_path: Path) -> None:
    """A config without the required ``bindings`` key fails fast."""
    config = tmp_path / "config.toml"
    config.write_text("modules = []\n")
    with pytest.raises(ConfigurationError, match="bindings"):
        Container.from_toml(config)


def test_from_toml_rejects_bindings_not_a_list(tmp_path: Path) -> None:
    """``bindings`` must be a list/array; a table is rejected."""
    config = tmp_path / "config.toml"
    config.write_text("[bindings]\nfoo = 'bar'\n")
    with pytest.raises(ConfigurationError, match="bindings"):
        Container.from_toml(config)


def test_from_toml_rejects_binding_missing_required_key(tmp_path: Path) -> None:
    """Every binding entry must have ``token``, ``factory`` and ``lifecycle``."""
    config = tmp_path / "config.toml"
    config.write_text(
        f"""
[[bindings]]
token = "{_FIXTURES}.FixtureClock"
lifecycle = "transient"
"""
    )
    with pytest.raises(ConfigurationError, match="factory"):
        Container.from_toml(config)


def test_from_toml_rejects_unknown_lifecycle(tmp_path: Path) -> None:
    """``lifecycle`` must be one of the known values."""
    config = tmp_path / "config.toml"
    config.write_text(
        f"""
[[bindings]]
token = "{_FIXTURES}.FixtureClock"
factory = "{_FIXTURES}.make_clock"
lifecycle = "perpetual"
"""
    )
    with pytest.raises(ConfigurationError, match="lifecycle"):
        Container.from_toml(config)


def test_from_toml_rejects_wrong_type_on_async_factory_flag(tmp_path: Path) -> None:
    """``async_factory`` must be a bool when present."""
    config = tmp_path / "config.toml"
    config.write_text(
        f"""
[[bindings]]
token = "{_FIXTURES}.FixtureClock"
factory = "{_FIXTURES}.make_clock"
lifecycle = "transient"
async_factory = "yes"
"""
    )
    with pytest.raises(ConfigurationError, match="async_factory"):
        Container.from_toml(config)


def test_from_toml_rejects_wrong_type_on_auto_inject_flag(tmp_path: Path) -> None:
    """``auto_inject`` must be a bool when present."""
    config = tmp_path / "config.toml"
    config.write_text(
        f"""
[[bindings]]
token = "{_FIXTURES}.FixtureClock"
factory = "{_FIXTURES}.make_clock"
lifecycle = "transient"
auto_inject = 1
"""
    )
    with pytest.raises(ConfigurationError, match="auto_inject"):
        Container.from_toml(config)


def test_from_toml_rejects_wrong_type_on_token(tmp_path: Path) -> None:
    """``token`` must be a string."""
    config = tmp_path / "config.toml"
    config.write_text(
        """
[[bindings]]
token = 42
factory = "x.y"
lifecycle = "transient"
"""
    )
    with pytest.raises(ConfigurationError, match="token"):
        Container.from_toml(config)


def test_from_toml_rejects_wrong_type_on_factory(tmp_path: Path) -> None:
    """``factory`` must be a string."""
    config = tmp_path / "config.toml"
    config.write_text(
        """
[[bindings]]
token = "x.y"
factory = 42
lifecycle = "transient"
"""
    )
    with pytest.raises(ConfigurationError, match="factory"):
        Container.from_toml(config)


def test_from_toml_rejects_binding_entry_not_a_table(tmp_path: Path) -> None:
    """Each binding entry must itself be a table."""
    from tripack_container.loaders import build_container_from_config

    with pytest.raises(ConfigurationError, match="must be a table"):
        build_container_from_config({"bindings": ["not-a-table"]})


def test_from_toml_rejects_modules_not_a_list(tmp_path: Path) -> None:
    """``modules`` must be a list of qualified names."""
    config = tmp_path / "config.toml"
    config.write_text(
        """
modules = "not-a-list"
bindings = []
"""
    )
    with pytest.raises(ConfigurationError, match="modules"):
        Container.from_toml(config)


def test_from_toml_rejects_modules_entry_not_a_string(tmp_path: Path) -> None:
    """Every modules entry must be a string."""
    from tripack_container.loaders import build_container_from_config

    with pytest.raises(ConfigurationError, match="modules"):
        build_container_from_config({"bindings": [], "modules": [42]})


# --- import errors --------------------------------------------------------


def test_from_toml_reports_clear_error_on_unimportable_factory(
    tmp_path: Path,
) -> None:
    """A factory whose module cannot be imported fails with ConfigurationError."""
    config = tmp_path / "config.toml"
    config.write_text(
        """
[[bindings]]
token = "x.y"
factory = "this_module_definitely_does_not_exist.make_clock"
lifecycle = "transient"
"""
    )
    with pytest.raises(ConfigurationError, match="Cannot import module"):
        Container.from_toml(config)


def test_from_toml_reports_clear_error_on_missing_attribute(
    tmp_path: Path,
) -> None:
    """A qualified name pointing to a missing attr fails clearly.

    The token must point at an importable module so the
    AttributeError surfaces on the factory lookup rather than
    short-circuiting on a token-side ImportError.
    """
    config = tmp_path / "config.toml"
    config.write_text(
        f"""
[[bindings]]
token = "{_FIXTURES}.FixtureClock"
factory = "{_FIXTURES}.no_such_attribute"
lifecycle = "transient"
"""
    )
    with pytest.raises(ConfigurationError, match="no attribute"):
        Container.from_toml(config)


def test_from_toml_reports_error_on_non_qualified_name(tmp_path: Path) -> None:
    """A name without a dot is not a qualified name and is rejected."""
    config = tmp_path / "config.toml"
    config.write_text(
        """
[[bindings]]
token = "bare"
factory = "x.y"
lifecycle = "transient"
"""
    )
    with pytest.raises(ConfigurationError, match="must include the module path"):
        Container.from_toml(config)


def test_from_toml_reports_error_on_non_module_in_modules(tmp_path: Path) -> None:
    """A modules entry that doesn't resolve to a Module-shaped object is rejected."""
    config = tmp_path / "config.toml"
    config.write_text(
        f"""
modules = ["{_FIXTURES}.make_clock"]
bindings = []
"""
    )
    with pytest.raises(ConfigurationError, match="Module-shaped"):
        Container.from_toml(config)
