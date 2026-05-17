# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Unit tests for :class:`tripack_contracts.BindingSpec` and
:class:`tripack_contracts.ContainerConfig`."""

from typing import Literal, is_typeddict

from tripack_contracts import BindingSpec, ContainerConfig


def test_binding_spec_is_a_typed_dict() -> None:
    """:class:`BindingSpec` is recognised as a :class:`TypedDict`."""
    assert is_typeddict(BindingSpec)


def test_container_config_is_a_typed_dict() -> None:
    """:class:`ContainerConfig` is recognised as a :class:`TypedDict`."""
    assert is_typeddict(ContainerConfig)


def test_minimal_binding_spec_constructs() -> None:
    """Only the three required keys yield a valid :class:`BindingSpec`."""
    spec: BindingSpec = {
        "token": "my_app.contracts.Clock",
        "factory": "my_app.factories.system_clock",
        "lifecycle": "singleton",
    }
    assert spec["token"] == "my_app.contracts.Clock"
    assert spec["factory"] == "my_app.factories.system_clock"
    assert spec["lifecycle"] == "singleton"


def test_full_binding_spec_constructs() -> None:
    """The optional keys are accepted when present."""
    spec: BindingSpec = {
        "token": "my_app.contracts.AsyncDb",
        "factory": "my_app.factories.async_db",
        "lifecycle": "singleton",
        "async_factory": True,
        "auto_inject": True,
    }
    assert spec["async_factory"] is True
    assert spec["auto_inject"] is True


def test_lifecycle_accepts_the_three_literal_values() -> None:
    """All three string literals are valid for ``lifecycle``."""
    valid_lifecycles: list[Literal["transient", "singleton", "scoped"]] = [
        "transient",
        "singleton",
        "scoped",
    ]
    for lc in valid_lifecycles:
        spec: BindingSpec = {
            "token": "my_app.contracts.Foo",
            "factory": "my_app.factories.foo",
            "lifecycle": lc,
        }
        assert spec["lifecycle"] == lc


def test_binding_spec_required_keys() -> None:
    """``__required_keys__`` exposes the three mandatory keys."""
    assert BindingSpec.__required_keys__ == frozenset({"token", "factory", "lifecycle"})


def test_binding_spec_optional_keys() -> None:
    """``__optional_keys__`` exposes the two ``NotRequired`` keys."""
    assert BindingSpec.__optional_keys__ == frozenset({"async_factory", "auto_inject"})


def test_minimal_container_config_constructs() -> None:
    """``bindings`` alone yields a valid :class:`ContainerConfig`."""
    config: ContainerConfig = {"bindings": []}
    assert config["bindings"] == []


def test_container_config_with_bindings() -> None:
    """A populated bindings list round-trips through the TypedDict."""
    config: ContainerConfig = {
        "bindings": [
            {
                "token": "my_app.contracts.Clock",
                "factory": "my_app.factories.system_clock",
                "lifecycle": "singleton",
            },
        ],
    }
    assert len(config["bindings"]) == 1
    assert config["bindings"][0]["token"] == "my_app.contracts.Clock"


def test_container_config_with_modules() -> None:
    """The ``modules`` optional key carries a list of dotted paths."""
    config: ContainerConfig = {
        "bindings": [],
        "modules": [
            "my_app.modules.persistence",
            "my_app.modules.logging",
        ],
    }
    assert config["modules"] == [
        "my_app.modules.persistence",
        "my_app.modules.logging",
    ]


def test_container_config_required_keys() -> None:
    """``bindings`` is required; ``modules`` is not."""
    assert ContainerConfig.__required_keys__ == frozenset({"bindings"})


def test_container_config_optional_keys() -> None:
    """``modules`` is the only ``NotRequired`` field."""
    assert ContainerConfig.__optional_keys__ == frozenset({"modules"})


def test_realistic_configuration_round_trip() -> None:
    """A representative end-to-end configuration constructs cleanly."""
    config: ContainerConfig = {
        "bindings": [
            {
                "token": "my_app.contracts.Clock",
                "factory": "my_app.factories.system_clock",
                "lifecycle": "singleton",
            },
            {
                "token": "my_app.contracts.Cache",
                "factory": "my_app.factories.memory_cache",
                "lifecycle": "scoped",
                "auto_inject": True,
            },
            {
                "token": "my_app.contracts.AsyncDb",
                "factory": "my_app.factories.async_db",
                "lifecycle": "singleton",
                "async_factory": True,
                "auto_inject": True,
            },
        ],
        "modules": ["my_app.modules.persistence"],
    }
    assert len(config["bindings"]) == 3
    assert config["modules"] == ["my_app.modules.persistence"]
