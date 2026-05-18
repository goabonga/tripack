# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Unit tests for automatic constructor / parameter injection (4.6).

This file deliberately avoids ``from __future__ import
annotations`` and keeps every test class at module level so
that :func:`inspect.get_annotations` can resolve string
annotations to actual types - nested-in-test-function classes
defined under future annotations would otherwise yield
unresolved name references at bind time.
"""

import asyncio

import pytest

from tripack_container import (
    Container,
    ContainerBuilder,
    async_singleton,
    inject,
    singleton,
)
from tripack_container.providers import INJECT_ATTR
from tripack_contracts import BindingError, Lifecycle, ResolutionError


class _Clock:
    """Framework-neutral leaf token (no constructor params)."""


class _Cache:
    """A second leaf token used to verify multi-param injection."""


class _Repository:
    """Leaf dependency for the nested-injection test."""


def _make_clock() -> _Clock:
    """Module-level sync factory for :class:`_Clock`."""
    return _Clock()


def _make_cache() -> _Cache:
    """Module-level sync factory for :class:`_Cache`."""
    return _Cache()


def _make_retries() -> int:
    """Module-level int factory used by the bound-default-override test."""
    return 42


class _App:
    """Service that depends on a Clock and a Cache via constructor injection."""

    def __init__(self, clock: _Clock, cache: _Cache) -> None:
        """Store the injected dependencies on the instance."""
        self.clock = clock
        self.cache = cache


class _Service:
    """Service that depends on :class:`_Repository` via constructor injection."""

    def __init__(self, repo: _Repository) -> None:
        """Store the injected repository on the instance."""
        self.repo = repo


class _ServiceWithDefault:
    """Constructor takes a required Clock and an optional retries int default."""

    def __init__(self, clock: _Clock, retries: int = 3) -> None:
        """Store both fields; ``retries`` keeps its default if int is unbound."""
        self.clock = clock
        self.retries = retries


class _ServiceWithRetries:
    """Same shape as :class:`_ServiceWithDefault`, used by the bound-int test."""

    def __init__(self, clock: _Clock, retries: int = 3) -> None:
        """Store both fields; ``retries`` is overridden when int is bound."""
        self.clock = clock
        self.retries = retries


class _Needs:
    """Service whose required dependency is left unbound on purpose."""

    def __init__(self, clock: _Clock) -> None:
        """Store the (unbound) clock so the resolve-time error fires here."""
        self.clock = clock


class _AsyncApp:
    """Service constructed by an async factory needing async deps."""

    def __init__(self, clock: _Clock) -> None:
        """Store the injected clock."""
        self.clock = clock


@inject
def _make_app_injected(clock: _Clock, cache: _Cache) -> _App:
    """Module-level :func:`inject`-tagged factory for the App service."""
    return _App(clock, cache)


@inject
def _make_service_injected(repo: _Repository) -> _Service:
    """:func:`inject`-tagged factory for the nested-injection test."""
    return _Service(repo)


@async_singleton
async def _make_clock_async() -> _Clock:
    """Module-level async factory used by the async injection test."""
    return _Clock()


@inject
async def _make_async_app(clock: _Clock) -> _AsyncApp:
    """Module-level async + :func:`inject` factory."""
    return _AsyncApp(clock)


@singleton
@inject
def _make_singleton_app(clock: _Clock, cache: _Cache) -> _App:
    """Stacked decorators: SINGLETON lifecycle + automatic injection."""
    return _App(clock, cache)


# Factory used by the bind-time-error tests. Defined with a full
# annotation so mypy strict is satisfied at parse time; the
# ``missing_anno`` annotation is then stripped so that
# ``inspect.signature`` sees an unannotated required parameter and
# the validator raises BindingError as the test expects. A smoke
# call before the strip covers the function body for the 100%
# coverage gate.
def _broken_factory(missing_anno: int) -> _Clock:
    """Factory whose ``missing_anno`` annotation gets stripped below."""
    return _Clock()


assert isinstance(_broken_factory(7), _Clock)
_broken_factory.__annotations__.pop("missing_anno", None)


# Same pattern for the unannotated-but-with-default case: the
# validator must SKIP the parameter rather than reject it, since
# the factory's own default fills the slot. Smoke-call covers the
# body before the annotation strip.
def _factory_with_unannotated_default(missing: int = 5) -> _Clock:
    """Factory whose ``missing`` annotation gets stripped while a default stays."""
    return _Clock()


assert isinstance(_factory_with_unannotated_default(), _Clock)
_factory_with_unannotated_default.__annotations__.pop("missing", None)


# --- @inject + Container.bind --------------------------------------------


def test_inject_decorator_attaches_marker_and_keeps_function_callable() -> None:
    """``@inject`` sets ``__tripack_inject__`` and leaves the function callable."""
    assert getattr(_make_app_injected, INJECT_ATTR) is True
    app = _make_app_injected(_Clock(), _Cache())
    assert isinstance(app, _App)


def test_container_bind_auto_injects_params_when_inject_marker_present() -> None:
    """A ``@inject``-marked factory has its params resolved from the container."""
    container = Container()
    container.bind(_Clock, _make_clock)
    container.bind(_Cache, _make_cache)
    container.bind(_App, _make_app_injected)
    app = container.resolve(_App)
    assert isinstance(app.clock, _Clock)
    assert isinstance(app.cache, _Cache)


def test_container_bind_explicit_auto_inject_keyword_drives_wrapping() -> None:
    """The explicit ``auto_inject=True`` keyword works without ``@inject``."""

    def _make_app(clock: _Clock, cache: _Cache) -> _App:
        return _App(clock, cache)

    container = Container()
    container.bind(_Clock, _make_clock)
    container.bind(_Cache, _make_cache)
    container.bind(_App, _make_app, auto_inject=True)
    app = container.resolve(_App)
    assert isinstance(app.clock, _Clock)
    assert isinstance(app.cache, _Cache)


def test_bind_class_registers_class_as_its_own_factory() -> None:
    """``bind_class`` resolves the constructor parameters from the container."""
    container = Container()
    container.bind(_Clock, _make_clock)
    container.bind(_Cache, _make_cache)
    container.bind_class(_App)
    app = container.resolve(_App)
    assert isinstance(app.clock, _Clock)
    assert isinstance(app.cache, _Cache)


def test_injection_chains_through_nested_dependencies() -> None:
    """End-to-end: an auto-injected service whose deps are also auto-injected."""
    container = Container()
    container.bind_class(_Repository)
    container.bind(_Service, _make_service_injected)
    service = container.resolve(_Service)
    assert isinstance(service.repo, _Repository)


def test_injection_keeps_default_when_dependency_is_not_bound() -> None:
    """A param with a default is left unfilled if its type is unbound."""
    container = Container()
    container.bind(_Clock, _make_clock)
    container.bind_class(_ServiceWithDefault)
    instance = container.resolve(_ServiceWithDefault)
    assert isinstance(instance.clock, _Clock)
    assert instance.retries == 3  # int unbound, default kept


def test_injection_uses_bound_int_when_available() -> None:
    """A param whose type IS bound is filled even when a default exists."""
    container = Container()
    container.bind(_Clock, _make_clock)
    container.bind(int, _make_retries)
    container.bind_class(_ServiceWithRetries)
    instance = container.resolve(_ServiceWithRetries)
    assert instance.retries == 42


def test_bindtime_error_raised_on_unannotated_required_param() -> None:
    """A param without annotation and without default fails at bind-time."""
    container = Container()
    with pytest.raises(BindingError, match="missing_anno"):
        container.bind(_Clock, _broken_factory, auto_inject=True)


def test_validator_skips_unannotated_param_with_default() -> None:
    """A param without annotation but WITH a default is skipped from the wrap.

    The validator allows the binding (no BindingError); the wrap
    sees an empty params list and calls the factory with no
    kwargs, letting its own default fill the slot.
    """
    container = Container()
    container.bind(_Clock, _factory_with_unannotated_default, auto_inject=True)
    assert isinstance(container.resolve(_Clock), _Clock)


def test_injection_raises_resolution_error_when_required_dep_is_unbound() -> None:
    """At resolve-time, a required (no-default) dep that is unbound bubbles up.

    Smoke-instantiates :class:`_Needs` first so its ``__init__``
    body is covered (the test below binds the class but never
    reaches its constructor because ResolutionError fires first).
    """
    needs = _Needs(_Clock())
    assert isinstance(needs.clock, _Clock)
    container = Container()
    container.bind_class(_Needs)  # _Clock NOT bound
    with pytest.raises(ResolutionError):
        container.resolve(_Needs)


# --- @inject + Builder ---------------------------------------------------


def test_builder_bind_class_auto_injects_via_build() -> None:
    """``ContainerBuilder.bind_class`` wraps at build-time with the new container."""
    container = (
        ContainerBuilder()
        .bind(_Clock, _make_clock, lifecycle=Lifecycle.SINGLETON)
        .bind(_Cache, _make_cache)
        .bind_class(_App)
        .build()
    )
    app = container.resolve(_App)
    assert isinstance(app.clock, _Clock)
    assert isinstance(app.cache, _Cache)


def test_builder_bind_with_inject_marker_picks_up_auto_inject() -> None:
    """The ``@inject`` marker is also honored on the builder path."""
    container = (
        ContainerBuilder()
        .bind(_Clock, _make_clock)
        .bind(_Cache, _make_cache)
        .bind(_App, _make_app_injected)
        .build()
    )
    app = container.resolve(_App)
    assert isinstance(app.clock, _Clock)


def test_builder_validates_signature_at_bind_time() -> None:
    """A broken factory passed to builder.bind raises at builder.bind time."""
    builder = ContainerBuilder()
    with pytest.raises(BindingError, match="missing_anno"):
        builder.bind(_Clock, _broken_factory, auto_inject=True)


async def _aresolve_builder_async() -> _Clock:
    """Coroutine helper: builder replays an async factory at build time."""
    container = (
        ContainerBuilder()
        .bind(_Clock, _make_clock_async, lifecycle=Lifecycle.SINGLETON)
        .build()
    )
    return await container.aresolve(_Clock)


def test_builder_build_replays_async_factories_correctly() -> None:
    """The build replay handles async bindings through the same Container.bind path."""
    instance = asyncio.run(_aresolve_builder_async())
    assert isinstance(instance, _Clock)


def test_builder_two_builds_have_independent_injection_wrappers() -> None:
    """Each build wraps factories with a closure over its own container."""
    builder = (
        ContainerBuilder()
        .bind(_Clock, _make_clock, lifecycle=Lifecycle.SINGLETON)
        .bind(_Cache, _make_cache, lifecycle=Lifecycle.SINGLETON)
        .bind_class(_App, lifecycle=Lifecycle.SINGLETON)
    )
    first = builder.build()
    second = builder.build()
    assert first.resolve(_App).clock is first.resolve(_Clock)
    assert second.resolve(_App).clock is second.resolve(_Clock)
    assert first.resolve(_App) is not second.resolve(_App)


# --- async path ----------------------------------------------------------


async def _aresolve_async_inject() -> _AsyncApp:
    """Coroutine helper for the async-injection test."""
    container = Container()
    container.bind(_Clock, _make_clock_async)
    container.bind(_AsyncApp, _make_async_app)
    return await container.aresolve(_AsyncApp)


def test_async_factory_with_inject_resolves_params_via_aresolve() -> None:
    """An async ``@inject`` factory has its params resolved via ``aresolve``."""
    app = asyncio.run(_aresolve_async_inject())
    assert isinstance(app.clock, _Clock)


class _AsyncServiceWithDefault:
    """Async service whose Clock dep is optional via a default of ``None``."""

    def __init__(self, clock: _Clock | None = None) -> None:
        """Store the (possibly ``None``) clock; default kicks in when unbound."""
        self.clock = clock


@inject
async def _make_async_service_with_default(
    clock: _Clock | None = None,
) -> _AsyncServiceWithDefault:
    """Async factory with an optional dep used to cover the async-default branch."""
    return _AsyncServiceWithDefault(clock)


async def _aresolve_async_with_unbound_default() -> _AsyncServiceWithDefault:
    """Coroutine helper covering the async ``default`` skip path."""
    container = Container()
    container.bind(_AsyncServiceWithDefault, _make_async_service_with_default)
    return await container.aresolve(_AsyncServiceWithDefault)


def test_async_injection_keeps_default_when_dependency_is_not_bound() -> None:
    """Async wrap: an unbound dep with a default falls back to that default."""
    instance = asyncio.run(_aresolve_async_with_unbound_default())
    assert instance.clock is None


@inject
async def _make_async_required_unbound(clock: _Clock) -> _AsyncApp:
    """Async factory with a required dep used to cover the async raise branch."""
    return _AsyncApp(clock)


# Smoke-await the factory body so coverage stays at 100% even
# though the failure-path test below raises before reaching the
# factory invocation.
assert isinstance(asyncio.run(_make_async_required_unbound(_Clock())), _AsyncApp)


async def _aresolve_async_required_unbound() -> _AsyncApp:
    """Coroutine helper: required dep is not bound so the async wrap re-raises."""
    container = Container()
    container.bind(_AsyncApp, _make_async_required_unbound)
    return await container.aresolve(_AsyncApp)


def test_async_injection_re_raises_resolution_error_for_required_unbound() -> None:
    """Async wrap: a required (no-default) unbound dep surfaces ResolutionError."""
    with pytest.raises(ResolutionError):
        asyncio.run(_aresolve_async_required_unbound())


# --- interaction with provider helpers -----------------------------------


def test_stacked_singleton_and_inject_markers_combine() -> None:
    """``@singleton`` and ``@inject`` stack: SINGLETON lifecycle + auto-injection."""
    container = Container()
    container.bind(_Clock, _make_clock)
    container.bind(_Cache, _make_cache)
    container.bind(_App, _make_singleton_app)
    first = container.resolve(_App)
    second = container.resolve(_App)
    assert first is second
    assert isinstance(first.clock, _Clock)
