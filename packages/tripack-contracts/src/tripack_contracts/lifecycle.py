# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Lifecycle enumeration for bindings.

A :class:`Lifecycle` decides how many times a binding's factory is
invoked and how long the resulting instance is cached. The three
values are deliberately stable across the framework - the runtime
maps each to a specific caching policy described in the per-value
docs of :doc:`docs/contracts/lifecycle`.
"""

from enum import StrEnum


class Lifecycle(StrEnum):
    """How long a resolved instance lives in the container.

    Inherits from :class:`enum.StrEnum` so members compare equal to
    their string value (``Lifecycle.TRANSIENT == "transient"``),
    serialise cleanly through JSON / TOML / YAML configuration
    loaders, and round-trip through ``str()`` without surprises.
    """

    TRANSIENT = "transient"
    """A fresh instance is produced on every resolution."""

    SINGLETON = "singleton"
    """One instance per container, cached after first resolution."""

    SCOPED = "scoped"
    """One instance per :class:`Scope`, cached within that scope."""
