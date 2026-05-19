# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""``Inject`` marker for ``Annotated[T, Inject]`` dependency injection.

Framework-agnostic primitive: the marker lives in
``tripack_container`` and carries no runtime behaviour on its
own. Per-framework adapters (FastAPI today, Starlette / pure
ASGI later) read the marker from annotations and translate it
to the host framework's dependency mechanism (``Depends`` in
FastAPI, request-state lookup in Starlette, ASGI scope walker,
...).

The marker accepts two shapes for ergonomics:

- Bare class - ``Annotated[Clock, Inject]`` resolves ``Clock``
  from the active container, raises if the token is not bound.
- Parameterised instance - ``Annotated[Clock, Inject(...)]``
  for the extended forms:

  - ``Inject(token="primary-clock")`` overrides the token
    (useful when the same Protocol is bound under a string-
    named key).
  - ``Inject(optional=True)`` returns ``None`` instead of
    raising on a missing binding. Pair with ``T | None`` in the
    annotation to keep mypy happy. ``T | None`` alone also
    implies ``optional=True`` without the explicit flag.
"""

import inspect
import types
from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, Annotated, Any, Union, get_args, get_origin

from tripack_contracts import ResolutionError, TripackError

if TYPE_CHECKING:
    from tripack_container.container import Container


class InjectionError(TripackError):
    """Raised when the injection machinery cannot run.

    Distinct from :class:`tripack_contracts.ResolutionError` (the
    binding is missing) and :class:`tripack_contracts.ScopeError`
    (no scope active for a SCOPED binding). ``InjectionError``
    fires when the *plumbing* of ``Annotated[T, Inject]`` itself
    fails to wire up - typically because no ``Container``
    instance is reachable at the call site, e.g. a
    ``TripackMiddleware`` invoked outside of an ASGI ``scope``
    that carries ``app.state.container``, or a lifespan
    decorated with :func:`tripack_lifespan` whose accessor
    returns ``None``.

    Subclassing :class:`TripackError` means every Tripack
    failure remains catchable through a single base type.
    """


class Inject:
    """Marker placed in ``Annotated[T, Inject]`` to opt into DI.

    Use the bare class for the common case, or instantiate to
    parametrise:

    - ``Annotated[Clock, Inject]`` - resolve ``Clock``.
    - ``Annotated[Clock | None, Inject]`` - resolve ``Clock``,
      return ``None`` on miss (implicit ``optional`` from the
      ``| None`` union).
    - ``Annotated[Clock, Inject(token="primary")]`` - resolve a
      named token instead of the annotation type.
    - ``Annotated[Notifier | None, Inject(optional=True)]`` -
      explicit optional flag (redundant with the ``| None``
      union but allowed for clarity).
    """

    __slots__ = ("optional", "token")

    token: object | None
    optional: bool

    def __init__(self, token: object | None = None, optional: bool = False) -> None:
        """Store the optional token override and the optional flag."""
        self.token = token
        self.optional = optional

    def __repr__(self) -> str:
        """Stable repr for error messages and debugging."""
        return f"Inject(token={self.token!r}, optional={self.optional!r})"


def _unwrap_optional(annotation: object) -> tuple[object, bool]:
    """Strip ``| None`` from a union; report whether it was present.

    Returns ``(inner, was_optional)``: ``T | None`` decays to
    ``(T, True)``; everything else passes through as
    ``(annotation, False)``. Used to derive the resolution
    token when the annotation is a binary union of ``T`` and
    ``None``; richer unions (``A | B | None``) are left as-is
    and reported as non-optional - the resolver will get the
    whole union as the token and most likely raise.
    """
    origin = get_origin(annotation)
    if origin is types.UnionType or origin is Union:
        non_none = tuple(a for a in get_args(annotation) if a is not type(None))
        if len(non_none) == 1:
            return non_none[0], True
    return annotation, False


def parse_inject_params(fn: Callable[..., Any]) -> dict[str, tuple[object, bool]]:
    """Return the ``{name: (token, optional)}`` map of inject-tagged params.

    Walks every parameter of ``fn``'s signature, looking up its
    annotation via :func:`inspect.get_annotations` (so ``from
    __future__ import annotations`` strings resolve to real
    types). Each ``Annotated[T, Inject]`` (or
    ``Annotated[T, Inject(...)]``) param contributes one entry;
    others are skipped.

    Used by every Tripack adapter that resolves injects at call
    time: :class:`tripack_container.fastapi._TripackRoute` for
    route handlers, :class:`TripackMiddleware.__call__` for
    middleware, the :class:`TripackAPI` lifespan composer for
    ``user_lifespan`` introspection, and the public
    :func:`tripack_lifespan` helper.

    The token defaults to ``T`` (with ``| None`` stripped) when
    the marker does not override; the optional flag is the
    union of the marker's ``optional=`` and the implicit
    ``T | None`` shape.
    """
    sig = inspect.signature(fn)
    hints = inspect.get_annotations(fn, eval_str=True)
    out: dict[str, tuple[object, bool]] = {}
    for name, param in sig.parameters.items():
        annotation = hints.get(name, param.annotation)
        parsed = parse_inject(annotation)
        if parsed is not None:
            out[name] = parsed
    return out


async def resolve_inject_kwargs(
    inject_params: Mapping[str, tuple[object, bool]],
    container: "Container | None",
) -> dict[str, Any]:
    """Resolve every entry of ``inject_params`` from ``container``.

    ``inject_params`` is the output of :func:`parse_inject_params`.
    For each ``(name, (token, optional))`` entry, calls
    ``container.aresolve(token)`` and returns the result keyed
    by ``name``. When ``optional`` is ``True`` and the binding
    is missing (``ResolutionError``), substitutes ``None``
    rather than propagating.

    Raises :class:`InjectionError` when ``container`` is
    ``None`` - the adapter's accessor failed to locate one. This
    is distinct from a missing binding (which would propagate
    ``ResolutionError``) and points the user at a wiring
    problem rather than a config problem.
    """
    if container is None:
        raise InjectionError(
            "No container is reachable from the injection site. "
            "Confirm that the lifespan ran (TripackAPI wires it "
            "automatically; pure-ASGI users compose "
            "`container_lifespan` themselves) and that any custom "
            "accessor returns the active Container."
        )
    out: dict[str, Any] = {}
    for name, (token, optional) in inject_params.items():
        try:
            out[name] = await container.aresolve(token)  # type: ignore[arg-type]
        except ResolutionError:
            if optional:
                out[name] = None
            else:
                raise
    return out


def parse_inject(annotation: object) -> tuple[object, bool] | None:
    """Return ``(token, optional)`` when ``annotation`` is an inject site.

    Walks an ``Annotated[T, ...]`` annotation; finds the bare
    ``Inject`` class or an ``Inject(...)`` instance in the
    metadata, derives the token (from the marker if it carries
    a ``token=``, otherwise from ``T`` with ``| None`` stripped),
    and derives the optional flag (explicit on the marker, or
    implicit from a ``T | None`` annotation).

    Returns ``None`` when the annotation is not an
    ``Annotated[..., Inject(...)]`` site, so the caller can
    fall through to normal parameter handling.
    """
    if get_origin(annotation) is not Annotated:
        return None
    args = get_args(annotation)
    typed = args[0]
    inner, was_optional = _unwrap_optional(typed)
    for meta in args[1:]:
        if meta is Inject:
            return inner, was_optional
        if isinstance(meta, Inject):
            token = meta.token if meta.token is not None else inner
            return token, meta.optional or was_optional
    return None
