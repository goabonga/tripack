# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Unit tests for :class:`tripack_runtime.DependencyGraph`."""

import pytest

from tripack_contracts import BindingError, Lifecycle, ResolutionError
from tripack_runtime import Binding, DependencyGraph


class _Clock:
    """Framework-neutral token target."""


class _Cache:
    """A second token target."""


def test_new_graph_is_empty() -> None:
    """A freshly constructed graph holds no bindings."""
    graph = DependencyGraph()
    assert len(graph) == 0
    assert list(graph) == []
    assert _Clock not in graph
    assert graph.bindings() == ()


def test_register_inserts_a_new_binding() -> None:
    """The first registration of a token stores the binding."""
    graph = DependencyGraph()
    binding = Binding(token=_Clock, factory=_Clock)
    graph.register(binding)
    assert len(graph) == 1
    assert _Clock in graph
    assert graph.lookup(_Clock) is binding


def test_register_is_idempotent_for_structurally_identical_bindings() -> None:
    """Re-registering an equal binding is a no-op, not a conflict."""
    graph = DependencyGraph()
    first = Binding(token=_Clock, factory=_Clock, lifecycle=Lifecycle.SINGLETON)
    second = Binding(token=_Clock, factory=_Clock, lifecycle=Lifecycle.SINGLETON)
    graph.register(first)
    graph.register(second)
    assert len(graph) == 1
    # The first registration wins; the second is silently equivalent.
    assert graph.lookup(_Clock) is first


def test_register_raises_on_conflicting_factory() -> None:
    """Two bindings with the same token but differing factories conflict."""

    class _OtherClock:
        pass

    graph = DependencyGraph()
    graph.register(Binding(token=_Clock, factory=_Clock))
    with pytest.raises(BindingError, match="Conflicting binding"):
        graph.register(Binding(token=_Clock, factory=_OtherClock))


def test_register_raises_on_conflicting_lifecycle() -> None:
    """Differing lifecycles on the same token are a conflict."""
    graph = DependencyGraph()
    graph.register(Binding(token=_Clock, factory=_Clock, lifecycle=Lifecycle.TRANSIENT))
    with pytest.raises(BindingError, match="Conflicting binding"):
        graph.register(
            Binding(token=_Clock, factory=_Clock, lifecycle=Lifecycle.SINGLETON)
        )


def test_register_raises_on_conflicting_auto_inject() -> None:
    """Differing ``auto_inject`` on the same token is a conflict."""
    graph = DependencyGraph()
    graph.register(Binding(token=_Clock, factory=_Clock, auto_inject=False))
    with pytest.raises(BindingError, match="Conflicting binding"):
        graph.register(Binding(token=_Clock, factory=_Clock, auto_inject=True))


def test_lookup_returns_registered_binding() -> None:
    """The binding round-trips through ``register`` then ``lookup``."""
    graph = DependencyGraph()
    binding = Binding(token=_Clock, factory=_Clock)
    graph.register(binding)
    assert graph.lookup(_Clock) is binding


def test_lookup_raises_resolution_error_on_unknown_token() -> None:
    """An unknown token causes :class:`ResolutionError`."""
    graph = DependencyGraph()
    with pytest.raises(ResolutionError, match="No binding registered"):
        graph.lookup(_Clock)


def test_lookup_preserves_the_keyerror_as_cause() -> None:
    """The chained ``KeyError`` is preserved for tracebacks."""
    graph = DependencyGraph()
    with pytest.raises(ResolutionError) as exc_info:
        graph.lookup(_Clock)
    assert isinstance(exc_info.value.__cause__, KeyError)


def test_register_supports_string_tokens() -> None:
    """String tokens coexist with class tokens in the same graph."""
    graph = DependencyGraph()
    binding = Binding(token="primary-clock", factory=_Clock)
    graph.register(binding)
    assert graph.lookup("primary-clock") is binding


def test_register_supports_tuple_tokens() -> None:
    """Composite hashable tokens (tuples) are accepted."""
    graph = DependencyGraph()
    token = ("clock", "primary")
    binding = Binding(token=token, factory=_Clock)
    graph.register(binding)
    assert graph.lookup(token) is binding


def test_distinct_tokens_coexist() -> None:
    """Class, string and tuple tokens are independent registry keys."""
    graph = DependencyGraph()
    class_binding = Binding(token=_Clock, factory=_Clock)
    string_binding = Binding(token="primary-clock", factory=_Clock)
    tuple_binding = Binding(token=("clock", "secondary"), factory=_Clock)
    graph.register(class_binding)
    graph.register(string_binding)
    graph.register(tuple_binding)
    assert len(graph) == 3
    assert graph.lookup(_Clock) is class_binding
    assert graph.lookup("primary-clock") is string_binding
    assert graph.lookup(("clock", "secondary")) is tuple_binding


def test_bindings_returns_snapshot_in_insertion_order() -> None:
    """``bindings()`` reflects the insertion order, frozen as a tuple."""
    graph = DependencyGraph()
    clock_binding = Binding(token=_Clock, factory=_Clock)
    cache_binding = Binding(token=_Cache, factory=_Cache)
    graph.register(clock_binding)
    graph.register(cache_binding)
    assert graph.bindings() == (clock_binding, cache_binding)


def test_iter_yields_registered_tokens_in_insertion_order() -> None:
    """Iterating the graph yields tokens in registration order."""
    graph = DependencyGraph()
    graph.register(Binding(token=_Clock, factory=_Clock))
    graph.register(Binding(token=_Cache, factory=_Cache))
    assert list(graph) == [_Clock, _Cache]


def test_contains_checks_token_presence() -> None:
    """``token in graph`` reflects current registration state."""
    graph = DependencyGraph()
    assert _Clock not in graph
    graph.register(Binding(token=_Clock, factory=_Clock))
    assert _Clock in graph


def test_graph_uses_slots_not_dict() -> None:
    """``__slots__`` keeps the graph instance free of per-instance dict."""
    graph = DependencyGraph()
    assert not hasattr(graph, "__dict__")
