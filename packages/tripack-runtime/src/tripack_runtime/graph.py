# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Dependency graph registry - the runtime's source of truth for bindings.

The :class:`DependencyGraph` is a token-keyed registry of
:class:`Binding` instances. It owns the data model; resolution
mechanics, caching, and scope handling live elsewhere and consult
this registry via :meth:`lookup`.

Registration semantics:

- ``register`` on an unknown token stores the binding.
- ``register`` on a known token with a **structurally identical**
  binding is a no-op (the registry is idempotent under
  re-registration).
- ``register`` on a known token with a **different** binding raises
  :class:`BindingError`, catching the conflict at registration time
  rather than at the first resolution.

Lookup semantics:

- ``lookup`` on a known token returns the registered binding.
- ``lookup`` on an unknown token raises :class:`ResolutionError`.

The graph is intentionally **not** thread-safe. Real-world containers
are typically built in a single thread at startup and only resolved
from afterwards; a concurrent-write story can be added later behind
the same surface if a use case materialises.
"""

from collections.abc import Iterator

from tripack_contracts import BindingError, DependencyToken, ResolutionError
from tripack_runtime.binding import Binding


class DependencyGraph:
    """Registry of :class:`Binding` instances keyed by token.

    The graph is the runtime's flat key-value store. Higher-level
    constructs (scopes, the resolver, the container's bind API) sit
    on top of it and never touch the underlying mapping directly.

    Example::

        from tripack_contracts import Lifecycle
        from tripack_runtime import Binding, DependencyGraph


        class Clock:
            pass


        graph = DependencyGraph()
        graph.register(Binding(token=Clock, factory=Clock,
                               lifecycle=Lifecycle.SINGLETON))
        binding = graph.lookup(Clock)
        assert binding.lifecycle == Lifecycle.SINGLETON
    """

    __slots__ = ("_bindings",)

    def __init__(self) -> None:
        """Create an empty graph."""
        self._bindings: dict[DependencyToken, Binding] = {}

    def register(self, binding: Binding) -> None:
        """Register ``binding`` under its declared ``token``.

        Idempotent: re-registering the same binding (structural
        equality) is a no-op. Conflicting registrations (same token,
        any other field differs) raise :class:`BindingError`.
        """
        existing = self._bindings.get(binding.token)
        if existing is None:
            self._bindings[binding.token] = binding
            return
        if existing == binding:
            return
        raise BindingError(
            f"Conflicting binding for token {binding.token!r}: "
            f"existing {existing!r}, new {binding!r}."
        )

    def lookup(self, token: DependencyToken) -> Binding:
        """Return the binding registered for ``token``.

        Raises :class:`ResolutionError` if no binding is registered.
        """
        try:
            return self._bindings[token]
        except KeyError as exc:
            raise ResolutionError(
                f"No binding registered for token {token!r}."
            ) from exc

    def bindings(self) -> tuple[Binding, ...]:
        """Return a snapshot of every currently-registered binding."""
        return tuple(self._bindings.values())

    def __len__(self) -> int:
        """Number of distinct tokens currently registered."""
        return len(self._bindings)

    def __contains__(self, token: object) -> bool:
        """Return whether ``token`` has a registered binding."""
        return token in self._bindings

    def __iter__(self) -> Iterator[DependencyToken]:
        """Iterate over the registered tokens in insertion order."""
        return iter(self._bindings)
