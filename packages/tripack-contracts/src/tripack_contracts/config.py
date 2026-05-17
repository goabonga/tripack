# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Declarative configuration schema for external loaders.

The two :class:`typing.TypedDict` types in this module describe the
shape of a Tripack container configuration as it is read from a
TOML, JSON or YAML file. The loaders themselves live in
``tripack-container``; this module is the **public schema** they
consume, so consumers can construct, validate or generate
configuration objects in typed Python before serialising them.

The shape mirrors the canonical layout::

    [[bindings]]
    token = "my_app.contracts.Clock"
    factory = "my_app.implementations.SystemClock"
    lifecycle = "singleton"

    [[bindings]]
    token = "my_app.contracts.Cache"
    factory = "my_app.factories.make_cache"
    lifecycle = "scoped"
    async_factory = true
    auto_inject = true

    modules = ["my_app.modules.persistence"]

TypedDicts have no runtime validation; the loaders perform schema
checks and raise :class:`ConfigurationError` on malformed input.
"""

from typing import Literal, NotRequired, TypedDict


class BindingSpec(TypedDict):
    """One binding entry in a declarative configuration file.

    Required keys:

    - ``token``: qualified dotted name of the token class, or an
      arbitrary string alias.
    - ``factory``: qualified dotted name of the callable that
      produces the bound instance.
    - ``lifecycle``: one of ``"transient"``, ``"singleton"``,
      ``"scoped"``. Mirrors :class:`Lifecycle` string values.

    Optional keys:

    - ``async_factory``: ``True`` when the factory is a coroutine
      (``async def``). Defaults to ``False`` when absent.
    - ``auto_inject``: ``True`` to request automatic constructor
      injection on the factory's parameters. Defaults to ``False``
      when absent.
    """

    token: str
    factory: str
    lifecycle: Literal["transient", "singleton", "scoped"]
    async_factory: NotRequired[bool]
    auto_inject: NotRequired[bool]


class ContainerConfig(TypedDict):
    """Root of a declarative container configuration.

    Required keys:

    - ``bindings``: ordered list of :class:`BindingSpec`. May be
      empty, but the key itself must be present so the loader can
      distinguish "empty container" from "malformed file".

    Optional keys:

    - ``modules``: list of qualified module names whose
      ``register(builder)`` callable is invoked when building the
      container. Modules apply before bindings, so module-defined
      tokens can be overridden by explicit ``[[bindings]]`` entries.
    """

    bindings: list[BindingSpec]
    modules: NotRequired[list[str]]
