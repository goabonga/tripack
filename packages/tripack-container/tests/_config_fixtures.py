# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Importable fixtures used by the TOML / JSON / YAML config tests.

The loaders resolve tokens and factories via dotted Python
names, so the tests need importable module-level
classes / functions / modules. Sharing them through a single
fixture module keeps the per-format test files focused on the
parser-specific behavior rather than re-declaring the wiring.
"""

from typing import Any

from tripack_contracts import Lifecycle


class FixtureClock:
    """Plain framework-neutral token used as a leaf service."""


class FixtureCache:
    """A second leaf token, used to verify multi-binding configs."""


def make_clock() -> FixtureClock:
    """Module-level sync factory for :class:`FixtureClock`."""
    return FixtureClock()


def make_cache() -> FixtureCache:
    """Module-level sync factory for :class:`FixtureCache`."""
    return FixtureCache()


async def make_clock_async() -> FixtureClock:
    """Module-level async factory for :class:`FixtureClock`."""
    return FixtureClock()


class FixtureModule:
    """Module that registers :class:`FixtureCache` on the builder."""

    def register(self, builder: Any) -> None:
        """Bind ``FixtureCache`` to ``make_cache``."""
        builder.bind(FixtureCache, make_cache, lifecycle=Lifecycle.SINGLETON)
