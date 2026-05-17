# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Immutable binding model.

A :class:`Binding` is the atomic registration unit the runtime keeps
in its dependency graph: a token, a factory (synchronous OR
asynchronous, exactly one of the two), the :class:`Lifecycle` that
governs caching, and an ``auto_inject`` flag the
:mod:`tripack_container` package consults to drive automatic
constructor injection.

The class is declared with ``frozen=True`` and ``slots=True`` so:

- registered bindings are immutable (no accidental in-place edits
  after registration);
- they are hashable, which lets the registry use them as keys in
  duplicate-detection sets;
- the memory footprint is minimal, since there is no per-instance
  ``__dict__``.

The XOR invariant on ``factory`` / ``async_factory`` is enforced
in ``__post_init__`` and raises :class:`BindingError` on violation -
catching the mistake at registration time rather than at the first
resolution attempt.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from tripack_contracts import BindingError, DependencyToken, Lifecycle


@dataclass(frozen=True, slots=True)
class Binding:
    """An immutable registration of a token, factory, and lifecycle.

    Construction-time invariants enforced in ``__post_init__``:

    - **Exactly one of** ``factory`` / ``async_factory`` is set.
      Both ``None`` is meaningless (no way to produce ``T``); both
      set is ambiguous (the runtime cannot guess which to call).

    Use the dataclass-generated equality, hashing, and ``replace``
    semantics. To "modify" an existing binding, build a new one with
    :func:`dataclasses.replace`; the original stays untouched.

    Example::

        from tripack_contracts import Lifecycle
        from tripack_runtime import Binding


        class Clock:
            def __init__(self) -> None:
                self.time = "12:00:00"


        binding = Binding(
            token=Clock,
            factory=Clock,
            lifecycle=Lifecycle.SINGLETON,
        )
    """

    token: DependencyToken
    factory: Callable[..., Any] | None = None
    async_factory: Callable[..., Awaitable[Any]] | None = None
    lifecycle: Lifecycle = Lifecycle.TRANSIENT
    auto_inject: bool = False

    def __post_init__(self) -> None:
        """Enforce the factory XOR async_factory invariant."""
        if (self.factory is None) == (self.async_factory is None):
            raise BindingError(
                "Exactly one of `factory` or `async_factory` must be set; "
                f"got factory={self.factory!r}, "
                f"async_factory={self.async_factory!r}."
            )
