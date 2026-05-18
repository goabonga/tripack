# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Shared fixtures for the workspace-wide integration test suite.

The integration tests resolve tokens through the **public API**
(``Container``, ``ContainerBuilder``, the provider helpers, the
config loaders), so the classes and factories they consume must
be importable by their dotted Python name - the config loaders
use :func:`importlib.import_module` plus :func:`getattr` to map
TOML / JSON / YAML strings back to live objects. Collecting the
shared shapes in this module keeps the per-scenario test files
focused on behavior rather than test stand-ins.

The names are deliberately framework-neutral
(``Clock``, ``Cache``, ``Logger``, ``App``, ``Pool``) to mirror
the documentation examples and to avoid suggesting that Tripack
ships any domain-specific service abstractions.
"""

from tripack_contracts import Lifecycle


class Clock:
    """Leaf token: a clock service with no dependencies."""


class Cache:
    """Leaf token: a cache service with no dependencies."""


class Logger:
    """Leaf token: a logger service with no dependencies."""


class App:
    """Composite service constructed from a ``Clock`` and a ``Cache``."""

    def __init__(self, clock: Clock, cache: Cache) -> None:
        """Store the injected dependencies on the instance."""
        self.clock = clock
        self.cache = cache


class Pool:
    """SINGLETON-typical resource that records its ``close`` calls."""

    def __init__(self) -> None:
        """Start with zero observed close calls."""
        self.close_calls = 0

    def close(self) -> None:
        """Idempotent bump of the call counter."""
        self.close_calls += 1


class Session:
    """SCOPED-typical resource that records its ``close`` calls."""

    def __init__(self) -> None:
        """Start with zero observed close calls."""
        self.close_calls = 0

    def close(self) -> None:
        """Idempotent bump of the call counter."""
        self.close_calls += 1


def make_clock() -> Clock:
    """Module-level factory for :class:`Clock` (TRANSIENT-friendly)."""
    return Clock()


def make_cache() -> Cache:
    """Module-level factory for :class:`Cache` (SINGLETON-friendly)."""
    return Cache()


def make_logger() -> Logger:
    """Module-level factory for :class:`Logger`."""
    return Logger()


def make_app(clock: Clock, cache: Cache) -> App:
    """Module-level factory for :class:`App`, takes two injected deps."""
    return App(clock, cache)


def make_pool() -> Pool:
    """Module-level factory for :class:`Pool`."""
    return Pool()


def make_session() -> Session:
    """Module-level factory for :class:`Session`."""
    return Session()


async def make_clock_async() -> Clock:
    """Module-level async factory for :class:`Clock`."""
    return Clock()


async def make_app_async(clock: Clock) -> App:
    """Module-level async factory for :class:`App`, takes one injected dep."""
    return App(clock, Cache())


class AppModule:
    """Reusable :class:`Module` bundle binding ``Clock`` and ``Cache``."""

    def register(self, builder: object) -> None:
        """Bind ``Clock`` and ``Cache`` on the builder.

        Typed against ``object`` rather than ``ContainerBuilder``
        to avoid a circular import through the fixtures module;
        the runtime shape is duck-typed by
        :meth:`ContainerBuilder.install`.
        """
        # mypy: the ``builder`` argument has ``bind`` at runtime
        # but its static type here is ``object``. The runtime
        # ``Module`` Protocol uses ``ContainerBuilder`` directly;
        # here we cast in the call site to keep the fixture
        # module free of a runtime import of the container.
        from tripack_container import ContainerBuilder

        assert isinstance(builder, ContainerBuilder)
        builder.bind(Clock, make_clock, lifecycle=Lifecycle.SINGLETON)
        builder.bind(Cache, make_cache, lifecycle=Lifecycle.SINGLETON)
