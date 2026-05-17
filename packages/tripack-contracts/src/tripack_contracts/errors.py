# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Public exception hierarchy for the Tripack framework.

Every error the framework raises is a subclass of :class:`TripackError`,
so consumers can catch the whole surface with a single ``except``
clause::

    try:
        container.resolve(Clock)
    except TripackError:
        ...

The hierarchy is intentionally shallow:

- :class:`TripackError`: root of the tree, abstract in spirit.
- :class:`ResolutionError`: a token could not be resolved.
- :class:`CircularDependencyError`: a cycle was detected during
  resolution. Subclass of :class:`ResolutionError` because the cycle
  is, semantically, a resolution failure.
- :class:`BindingError`: a binding could not be registered.
- :class:`ScopeError`: a scope reference is unknown or no longer
  valid.
- :class:`ConfigurationError`: declarative configuration is invalid
  or unloadable.

All classes are picklable, including :class:`CircularDependencyError`,
which uses a custom ``__reduce__`` to round-trip its ``cycle``
attribute.
"""

from collections.abc import Sequence
from typing import Any

from tripack_contracts.types import DependencyToken


class TripackError(Exception):
    """Base class for all Tripack-defined exceptions.

    Do not raise this directly; use one of the more specific
    subclasses below. Catching this base lets consumers handle every
    framework error with a single ``except`` clause.
    """


class ResolutionError(TripackError):
    """Raised when the runtime cannot resolve a token to an instance.

    Typical causes:

    - the token has no binding registered in the container;
    - the binding's factory raised and the cache was not poisoned.
    """


class BindingError(TripackError):
    """Raised when a binding cannot be registered.

    Typical causes:

    - registering a token that conflicts with a previous binding;
    - registering a binding whose factory signature is incompatible
      with the declared lifecycle;
    - violating the idempotency contract (same token, different
      factory).
    """


class ScopeError(TripackError):
    """Raised when a scope reference is unknown or expired.

    Typical causes:

    - resolving a ``SCOPED`` binding without entering a scope first;
    - using a scope token after its context manager has exited.
    """


class ConfigurationError(TripackError):
    """Raised when declarative configuration is invalid or unloadable.

    Typical causes:

    - the configuration file is malformed (TOML / JSON / YAML
      parsing failure);
    - the schema is invalid (missing keys, wrong types);
    - a callable referenced by qualified name cannot be imported.
    """


class CircularDependencyError(ResolutionError):
    """Raised when token resolution detects a cycle.

    The ``cycle`` attribute carries the ordered chain of tokens
    forming the loop. By convention, the first and last entries are
    the same token::

        A -> B -> C -> A

    The exception message renders the cycle as a readable path
    (using ``__qualname__`` for class tokens and ``repr`` for other
    hashables).
    """

    cycle: tuple[DependencyToken, ...]

    def __init__(self, cycle: Sequence[DependencyToken]) -> None:
        self.cycle = tuple(cycle)
        super().__init__(self._format_cycle(self.cycle))

    @staticmethod
    def _format_cycle(cycle: tuple[DependencyToken, ...]) -> str:
        names = [CircularDependencyError._format_token(t) for t in cycle]
        return "Circular dependency detected: " + " -> ".join(names)

    @staticmethod
    def _format_token(token: DependencyToken) -> str:
        if isinstance(token, type):
            return token.__qualname__
        return repr(token)

    def __reduce__(self) -> tuple[Any, tuple[tuple[DependencyToken, ...]]]:
        """Round-trip the ``cycle`` attribute through :mod:`pickle`."""
        return (type(self), (self.cycle,))
