# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Unit tests for :meth:`Container.from_json` (4.10).

Validation behavior is covered exhaustively in the TOML test
file via direct calls into :func:`build_container_from_config`;
this file focuses on the JSON-parsing path and the JSON-specific
error wrapping.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import _config_fixtures as fixtures
import pytest

from tripack_container import Container
from tripack_contracts import ConfigurationError

_FIXTURES = fixtures.__name__


def _dump_json(path: Path, data: object) -> Path:
    """Write ``data`` as JSON into ``path`` and return the path."""
    path.write_text(json.dumps(data))
    return path


def test_from_json_loads_a_simple_singleton_binding(tmp_path: Path) -> None:
    """A minimal JSON config produces a working SINGLETON binding."""
    config = _dump_json(
        tmp_path / "config.json",
        {
            "bindings": [
                {
                    "token": f"{_FIXTURES}.FixtureClock",
                    "factory": f"{_FIXTURES}.make_clock",
                    "lifecycle": "singleton",
                }
            ]
        },
    )
    container = Container.from_json(config)
    first = container.resolve(fixtures.FixtureClock)
    second = container.resolve(fixtures.FixtureClock)
    assert isinstance(first, fixtures.FixtureClock)
    assert first is second


def test_from_json_loads_multiple_bindings_in_one_file(tmp_path: Path) -> None:
    """Two binding entries each register on the container."""
    config = _dump_json(
        tmp_path / "config.json",
        {
            "bindings": [
                {
                    "token": f"{_FIXTURES}.FixtureClock",
                    "factory": f"{_FIXTURES}.make_clock",
                    "lifecycle": "transient",
                },
                {
                    "token": f"{_FIXTURES}.FixtureCache",
                    "factory": f"{_FIXTURES}.make_cache",
                    "lifecycle": "singleton",
                },
            ]
        },
    )
    container = Container.from_json(config)
    assert isinstance(container.resolve(fixtures.FixtureClock), fixtures.FixtureClock)
    assert isinstance(container.resolve(fixtures.FixtureCache), fixtures.FixtureCache)


async def _aresolve_async_from_json(config: Path) -> fixtures.FixtureClock:
    """Coroutine helper: load + aresolve an async-factory JSON config."""
    container = Container.from_json(config)
    return await container.aresolve(fixtures.FixtureClock)


def test_from_json_supports_async_factories(tmp_path: Path) -> None:
    """An async factory registered via JSON resolves through ``aresolve``."""
    config = _dump_json(
        tmp_path / "config.json",
        {
            "bindings": [
                {
                    "token": f"{_FIXTURES}.FixtureClock",
                    "factory": f"{_FIXTURES}.make_clock_async",
                    "lifecycle": "transient",
                }
            ]
        },
    )
    instance = asyncio.run(_aresolve_async_from_json(config))
    assert isinstance(instance, fixtures.FixtureClock)


def test_from_json_installs_a_module(tmp_path: Path) -> None:
    """The ``modules`` array runs each module's ``register`` on build."""
    config = _dump_json(
        tmp_path / "config.json",
        {
            "modules": [f"{_FIXTURES}.FixtureModule"],
            "bindings": [],
        },
    )
    container = Container.from_json(config)
    assert isinstance(container.resolve(fixtures.FixtureCache), fixtures.FixtureCache)


def test_from_json_wraps_decode_errors_in_configuration_error(tmp_path: Path) -> None:
    """A malformed JSON file surfaces as ConfigurationError, not JSONDecodeError."""
    config = tmp_path / "config.json"
    config.write_text("{this is not valid json")
    with pytest.raises(ConfigurationError, match="Failed to parse JSON"):
        Container.from_json(config)


def test_from_json_uses_the_same_validation_as_toml(tmp_path: Path) -> None:
    """Validation reuses the shared helper, so the same errors surface."""
    config = _dump_json(
        tmp_path / "config.json",
        {
            "bindings": [
                {
                    "token": f"{_FIXTURES}.FixtureClock",
                    "factory": f"{_FIXTURES}.make_clock",
                    "lifecycle": "perpetual",  # unknown
                }
            ]
        },
    )
    with pytest.raises(ConfigurationError, match="lifecycle"):
        Container.from_json(config)
