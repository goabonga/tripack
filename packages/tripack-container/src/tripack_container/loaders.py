# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Declarative configuration loaders for the container.

Configuration is described against the
:class:`tripack_contracts.ContainerConfig` TypedDict: a list of
binding specs (token + factory + lifecycle + optional flags) and
an optional list of module qualified names. Every reference -
tokens, factories, modules - is given as a dotted Python name
that :func:`importlib.import_module` plus :func:`getattr`
resolves to an actual object.

The 4.9 commit ships :func:`load_toml`; 4.10 adds the JSON
counterpart and 4.11 the optional YAML one. Every loader shares
the same :func:`_validate_container_config` /
:func:`_import_qualified` helpers, so the strict-validation
guarantees and import-error semantics are identical across
formats.

Validation runs **before** any binding is applied to a builder,
so a structurally bad config raises
:class:`tripack_contracts.ConfigurationError` without producing
a half-wired container. Import errors surface the same way -
the loader never leaks a partially populated container.
"""

import importlib
import json
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, cast

from tripack_contracts import (
    BindingSpec,
    ConfigurationError,
    ContainerConfig,
    Lifecycle,
)

_LifecycleLiteral = Literal["transient", "singleton", "scoped"]

if TYPE_CHECKING:
    from tripack_container.container import Container

_VALID_LIFECYCLE_VALUES: frozenset[str] = frozenset(lc.value for lc in Lifecycle)


def _import_qualified(name: str) -> Any:
    """Resolve a dotted name to a Python object.

    Accepts ``"pkg.mod.attr"`` and looks up ``attr`` on
    ``importlib.import_module("pkg.mod")``. Wraps both the
    import failure and the missing-attribute failure into a
    :class:`tripack_contracts.ConfigurationError` so consumers
    can catch a single exception type.
    """
    if "." not in name:
        raise ConfigurationError(
            f"Qualified name {name!r} must include the module path "
            "(e.g. 'my_app.factories.make_clock')."
        )
    module_path, _, attr_name = name.rpartition(".")
    try:
        module = importlib.import_module(module_path)
    except ImportError as exc:
        raise ConfigurationError(
            f"Cannot import module {module_path!r} for qualified name {name!r}: {exc}."
        ) from exc
    try:
        return getattr(module, attr_name)
    except AttributeError as exc:
        raise ConfigurationError(
            f"Module {module_path!r} has no attribute {attr_name!r}."
        ) from exc


def _validate_binding_spec(raw: object, index: int) -> BindingSpec:
    """Validate one binding entry from the parsed config.

    Returns a properly typed :class:`BindingSpec`; raises
    :class:`ConfigurationError` on any structural problem
    (missing key, wrong type, unknown lifecycle value).
    """
    if not isinstance(raw, dict):
        raise ConfigurationError(
            f"bindings[{index}] must be a table; got {type(raw).__name__}."
        )
    for key in ("token", "factory", "lifecycle"):
        if key not in raw:
            raise ConfigurationError(
                f"bindings[{index}] is missing required key {key!r}."
            )
    token = raw["token"]
    factory = raw["factory"]
    lifecycle = raw["lifecycle"]
    if not isinstance(token, str):
        raise ConfigurationError(
            f"bindings[{index}].token must be a string; got {type(token).__name__}."
        )
    if not isinstance(factory, str):
        raise ConfigurationError(
            f"bindings[{index}].factory must be a string; got {type(factory).__name__}."
        )
    if not isinstance(lifecycle, str) or lifecycle not in _VALID_LIFECYCLE_VALUES:
        raise ConfigurationError(
            f"bindings[{index}].lifecycle must be one of "
            f"{sorted(_VALID_LIFECYCLE_VALUES)}; got {lifecycle!r}."
        )
    async_factory = raw.get("async_factory", False)
    if not isinstance(async_factory, bool):
        raise ConfigurationError(
            f"bindings[{index}].async_factory must be a bool; got "
            f"{type(async_factory).__name__}."
        )
    auto_inject = raw.get("auto_inject", False)
    if not isinstance(auto_inject, bool):
        raise ConfigurationError(
            f"bindings[{index}].auto_inject must be a bool; got "
            f"{type(auto_inject).__name__}."
        )
    spec: BindingSpec = {
        "token": token,
        "factory": factory,
        # Membership in ``_VALID_LIFECYCLE_VALUES`` was checked
        # above; cast narrows the runtime ``str`` to the
        # ``Literal`` form ``BindingSpec`` requires for mypy.
        "lifecycle": cast("_LifecycleLiteral", lifecycle),
        "async_factory": async_factory,
        "auto_inject": auto_inject,
    }
    return spec


def _validate_container_config(data: object) -> ContainerConfig:
    """Validate a parsed config dict against :class:`ContainerConfig`.

    The strict-typing pass keeps :func:`build_container_from_config`
    free of inline ``isinstance`` checks; once validation passes
    every field is the right shape for the downstream loader.
    """
    if not isinstance(data, dict):
        raise ConfigurationError(
            "Container config must be a table at the top level; got "
            f"{type(data).__name__}."
        )
    if "bindings" not in data:
        raise ConfigurationError("Container config missing required key 'bindings'.")
    raw_bindings = data["bindings"]
    if not isinstance(raw_bindings, list):
        raise ConfigurationError(
            f"Container config 'bindings' must be a list; got "
            f"{type(raw_bindings).__name__}."
        )
    validated_bindings = [
        _validate_binding_spec(entry, index) for index, entry in enumerate(raw_bindings)
    ]
    modules_raw = data.get("modules", [])
    if not isinstance(modules_raw, list):
        raise ConfigurationError(
            f"Container config 'modules' must be a list of qualified names; "
            f"got {type(modules_raw).__name__}."
        )
    for index, name in enumerate(modules_raw):
        if not isinstance(name, str):
            raise ConfigurationError(
                f"modules[{index}] must be a string; got {type(name).__name__}."
            )
    config: ContainerConfig = {
        "bindings": validated_bindings,
        "modules": list(modules_raw),
    }
    return config


def build_container_from_config(data: object) -> "Container":
    """Validate ``data`` and assemble a sealed :class:`Container` from it.

    Used by every format-specific loader (TOML in 4.9, JSON in
    4.10, YAML in 4.11). Validation runs first; binding and
    module registration run on a fresh :class:`ContainerBuilder`;
    the final :meth:`ContainerBuilder.build` returns a sealed
    container.
    """
    # Imported lazily to break a circular dependency: container.py
    # imports loaders.py for its from_toml classmethod, and
    # loaders.py needs the builder type at runtime.
    from tripack_container.builder import ContainerBuilder

    validated = _validate_container_config(data)
    builder = ContainerBuilder()
    for module_name in validated.get("modules", []):
        module_obj = _import_qualified(module_name)
        # Accept either an already-built Module instance or a class
        # whose no-arg constructor produces one (the common case).
        if isinstance(module_obj, type):
            module_obj = module_obj()
        # Duck-type check rather than ``isinstance(.., Module)``
        # because the Module Protocol is intentionally not
        # ``@runtime_checkable``.
        if not callable(getattr(module_obj, "register", None)):
            raise ConfigurationError(
                f"modules entry {module_name!r} did not resolve to a "
                "Module-shaped object (no callable 'register')."
            )
        builder.install(module_obj)
    for spec in validated["bindings"]:
        token = _import_qualified(spec["token"])
        factory = _import_qualified(spec["factory"])
        builder.bind(
            token,
            factory,
            lifecycle=Lifecycle(spec["lifecycle"]),
            auto_inject=spec.get("auto_inject", False),
        )
    return builder.build()


def load_toml(path: str | Path) -> "Container":
    """Load and build a :class:`Container` from a TOML file.

    Uses the standard-library :mod:`tomllib` (no extra
    dependency). Parsing happens on the binary content so TOML's
    UTF-8 / BOM rules are respected automatically; validation
    runs before any binding is applied so a structurally bad
    config raises :class:`ConfigurationError` without producing
    a half-wired container.
    """
    with Path(path).open("rb") as fp:
        data = tomllib.load(fp)
    return build_container_from_config(data)


def load_json(path: str | Path) -> "Container":
    """Load and build a :class:`Container` from a JSON file.

    Uses the standard-library :mod:`json` (no extra
    dependency). A malformed JSON file raises
    :class:`tripack_contracts.ConfigurationError` with the
    decoder's message attached so the caller does not have to
    catch :class:`json.JSONDecodeError` separately. Otherwise
    the structural validation and builder assembly mirror
    :func:`load_toml`.
    """
    try:
        with Path(path).open() as fp:
            data = json.load(fp)
    except json.JSONDecodeError as exc:
        raise ConfigurationError(
            f"Failed to parse JSON config at {path!r}: {exc}."
        ) from exc
    return build_container_from_config(data)


def load_yaml(path: str | Path) -> "Container":
    """Load and build a :class:`Container` from a YAML file.

    Requires the optional ``yaml`` extra
    (``pip install tripack-container[yaml]``), which pulls in
    PyYAML. Without the extra, the import fails with a clear
    :class:`tripack_contracts.ConfigurationError` pointing at
    the install command rather than the bare
    :class:`ModuleNotFoundError`. With the extra, the file is
    parsed via :func:`yaml.safe_load` (so arbitrary Python
    objects cannot be deserialised) and run through the same
    :func:`build_container_from_config` pipeline as TOML and
    JSON.
    """
    try:
        import yaml
    except ImportError as exc:
        raise ConfigurationError(
            "YAML support requires the optional 'yaml' extra: "
            "install with `pip install tripack-container[yaml]`."
        ) from exc
    try:
        with Path(path).open() as fp:
            data = yaml.safe_load(fp)
    except yaml.YAMLError as exc:
        raise ConfigurationError(
            f"Failed to parse YAML config at {path!r}: {exc}."
        ) from exc
    return build_container_from_config(data)
