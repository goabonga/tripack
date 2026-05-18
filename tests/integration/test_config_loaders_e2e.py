# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""End-to-end TOML / JSON / YAML config loading through the public API."""

from __future__ import annotations

import json
from pathlib import Path

import _fixtures as F

from tripack_container import Container

_FIXTURES = F.__name__


# --- TOML -----------------------------------------------------------------


def test_from_toml_loads_a_multi_binding_container_end_to_end(
    tmp_path: Path,
) -> None:
    """A TOML config with TRANSIENT + SINGLETON bindings produces a live container."""
    config = tmp_path / "config.toml"
    config.write_text(
        f"""
[[bindings]]
token = "{_FIXTURES}.Clock"
factory = "{_FIXTURES}.make_clock"
lifecycle = "transient"

[[bindings]]
token = "{_FIXTURES}.Cache"
factory = "{_FIXTURES}.make_cache"
lifecycle = "singleton"
"""
    )
    container = Container.from_toml(config)
    assert isinstance(container.resolve(F.Clock), F.Clock)
    assert container.resolve(F.Cache) is container.resolve(F.Cache)


# --- JSON -----------------------------------------------------------------


def test_from_json_loads_a_module_powered_container_end_to_end(
    tmp_path: Path,
) -> None:
    """JSON config can install Modules just like TOML and YAML."""
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps(
            {
                "modules": [f"{_FIXTURES}.AppModule"],
                "bindings": [],
            }
        )
    )
    container = Container.from_json(config)
    # The AppModule binds both Clock and Cache.
    assert isinstance(container.resolve(F.Clock), F.Clock)
    assert isinstance(container.resolve(F.Cache), F.Cache)


# --- YAML -----------------------------------------------------------------


def test_from_yaml_loads_an_async_factory_container_end_to_end(
    tmp_path: Path,
) -> None:
    """A YAML config can register an async factory that is driven via ``aresolve``."""
    import asyncio

    config = tmp_path / "config.yaml"
    config.write_text(
        f"""
bindings:
  - token: {_FIXTURES}.Clock
    factory: {_FIXTURES}.make_clock_async
    lifecycle: singleton
"""
    )

    async def _drive() -> F.Clock:
        container = Container.from_yaml(config)
        return await container.aresolve(F.Clock)

    instance = asyncio.run(_drive())
    assert isinstance(instance, F.Clock)


# --- Cross-format parity --------------------------------------------------


def test_three_formats_produce_equivalent_containers(tmp_path: Path) -> None:
    """The same logical config in TOML / JSON / YAML yields the same wiring."""
    toml_path = tmp_path / "config.toml"
    toml_path.write_text(
        f"""
[[bindings]]
token = "{_FIXTURES}.Clock"
factory = "{_FIXTURES}.make_clock"
lifecycle = "singleton"
"""
    )
    json_path = tmp_path / "config.json"
    json_path.write_text(
        json.dumps(
            {
                "bindings": [
                    {
                        "token": f"{_FIXTURES}.Clock",
                        "factory": f"{_FIXTURES}.make_clock",
                        "lifecycle": "singleton",
                    }
                ]
            }
        )
    )
    yaml_path = tmp_path / "config.yaml"
    yaml_path.write_text(
        f"""
bindings:
  - token: {_FIXTURES}.Clock
    factory: {_FIXTURES}.make_clock
    lifecycle: singleton
"""
    )

    toml_container = Container.from_toml(toml_path)
    json_container = Container.from_json(json_path)
    yaml_container = Container.from_yaml(yaml_path)

    # Each container caches its OWN singleton (independent state).
    toml_clock = toml_container.resolve(F.Clock)
    json_clock = json_container.resolve(F.Clock)
    yaml_clock = yaml_container.resolve(F.Clock)
    assert isinstance(toml_clock, F.Clock)
    assert isinstance(json_clock, F.Clock)
    assert isinstance(yaml_clock, F.Clock)
    # SINGLETON is per-container: three distinct instances.
    assert toml_clock is not json_clock
    assert json_clock is not yaml_clock
    # And within one container, the singleton is shared.
    assert toml_container.resolve(F.Clock) is toml_clock
