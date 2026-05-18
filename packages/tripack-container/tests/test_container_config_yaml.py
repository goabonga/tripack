# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Unit tests for :meth:`Container.from_yaml` (4.11)."""

from __future__ import annotations

import asyncio
import builtins
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import _config_fixtures as fixtures
import pytest

from tripack_container import Container
from tripack_contracts import ConfigurationError

_FIXTURES = fixtures.__name__


def _write(path: Path, body: str) -> Path:
    """Write ``body`` to ``path`` and return the path."""
    path.write_text(body)
    return path


def test_from_yaml_loads_a_simple_singleton_binding(tmp_path: Path) -> None:
    """A minimal YAML config produces a working SINGLETON binding."""
    config = _write(
        tmp_path / "config.yaml",
        f"""
bindings:
  - token: {_FIXTURES}.FixtureClock
    factory: {_FIXTURES}.make_clock
    lifecycle: singleton
""",
    )
    container = Container.from_yaml(config)
    first = container.resolve(fixtures.FixtureClock)
    second = container.resolve(fixtures.FixtureClock)
    assert isinstance(first, fixtures.FixtureClock)
    assert first is second


def test_from_yaml_loads_multiple_bindings_in_one_file(tmp_path: Path) -> None:
    """Two binding entries each register on the container."""
    config = _write(
        tmp_path / "config.yaml",
        f"""
bindings:
  - token: {_FIXTURES}.FixtureClock
    factory: {_FIXTURES}.make_clock
    lifecycle: transient
  - token: {_FIXTURES}.FixtureCache
    factory: {_FIXTURES}.make_cache
    lifecycle: singleton
""",
    )
    container = Container.from_yaml(config)
    assert isinstance(container.resolve(fixtures.FixtureClock), fixtures.FixtureClock)
    assert isinstance(container.resolve(fixtures.FixtureCache), fixtures.FixtureCache)


async def _aresolve_async_from_yaml(config: Path) -> fixtures.FixtureClock:
    """Coroutine helper: load + aresolve an async-factory YAML config."""
    container = Container.from_yaml(config)
    return await container.aresolve(fixtures.FixtureClock)


def test_from_yaml_supports_async_factories(tmp_path: Path) -> None:
    """An async factory registered via YAML resolves through ``aresolve``."""
    config = _write(
        tmp_path / "config.yaml",
        f"""
bindings:
  - token: {_FIXTURES}.FixtureClock
    factory: {_FIXTURES}.make_clock_async
    lifecycle: transient
""",
    )
    instance = asyncio.run(_aresolve_async_from_yaml(config))
    assert isinstance(instance, fixtures.FixtureClock)


def test_from_yaml_installs_a_module(tmp_path: Path) -> None:
    """The ``modules`` list runs each module's ``register`` on build."""
    config = _write(
        tmp_path / "config.yaml",
        f"""
modules:
  - {_FIXTURES}.FixtureModule
bindings: []
""",
    )
    container = Container.from_yaml(config)
    assert isinstance(container.resolve(fixtures.FixtureCache), fixtures.FixtureCache)


def test_from_yaml_wraps_parse_errors_in_configuration_error(tmp_path: Path) -> None:
    """A malformed YAML file surfaces as ConfigurationError, not YAMLError."""
    config = _write(
        tmp_path / "config.yaml",
        # Tab-indent inside a flow collection is a YAML syntax error
        # in PyYAML's strict mode.
        "bindings: [\n\t- not-valid-yaml\n]",
    )
    with pytest.raises(ConfigurationError, match="Failed to parse YAML"):
        Container.from_yaml(config)


def test_from_yaml_uses_the_same_validation_as_toml(tmp_path: Path) -> None:
    """Validation reuses the shared helper, so the same errors surface."""
    config = _write(
        tmp_path / "config.yaml",
        f"""
bindings:
  - token: {_FIXTURES}.FixtureClock
    factory: {_FIXTURES}.make_clock
    lifecycle: perpetual
""",
    )
    with pytest.raises(ConfigurationError, match="lifecycle"):
        Container.from_yaml(config)


def test_from_yaml_raises_clear_error_when_pyyaml_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without the ``yaml`` extra, the call points at the install command.

    Forces a fresh ``import yaml`` failure inside :func:`load_yaml`
    by removing the module from :data:`sys.modules` and patching
    :func:`builtins.__import__` to reject the lookup.
    """
    config = _write(
        tmp_path / "config.yaml",
        f"""
bindings:
  - token: {_FIXTURES}.FixtureClock
    factory: {_FIXTURES}.make_clock
    lifecycle: transient
""",
    )
    monkeypatch.delitem(sys.modules, "yaml", raising=False)
    real_import = builtins.__import__

    def _fail_yaml_import(
        name: str,
        globals_dict: Mapping[str, object] | None = None,
        locals_dict: Mapping[str, object] | None = None,
        fromlist: Sequence[str] = (),
        level: int = 0,
    ) -> Any:
        """Reject ``import yaml`` while leaving every other import alone."""
        if name == "yaml":
            raise ImportError("simulated absence of pyyaml")
        return real_import(name, globals_dict, locals_dict, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _fail_yaml_import)
    with pytest.raises(ConfigurationError, match="install with"):
        Container.from_yaml(config)
