# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Tests for the ``Inject`` marker and ``parse_inject`` helper.

Cover the four ergonomic forms supported by the marker:

- bare class - ``Annotated[T, Inject]``
- instance default - ``Annotated[T, Inject()]``
- token override - ``Annotated[T, Inject(token=...)]``
- optional flag - ``Annotated[T | None, Inject]`` / ``Inject(optional=True)``

plus the non-inject case (``parse_inject`` returns ``None``).
"""

from typing import Annotated

import pytest

from tripack_container import (
    ContainerBuilder,
    Inject,
    InjectionError,
)
from tripack_container._inject import (
    parse_inject,
    parse_inject_params,
    resolve_inject_kwargs,
)
from tripack_contracts import Lifecycle, ResolutionError


class Clock:
    """Stand-in token for tests; the marker doesn't care about behaviour."""


def test_inject_bare_class_returns_token_and_not_optional() -> None:
    result = parse_inject(Annotated[Clock, Inject])
    assert result == (Clock, False)


def test_inject_default_instance_returns_token_and_not_optional() -> None:
    result = parse_inject(Annotated[Clock, Inject()])
    assert result == (Clock, False)


def test_inject_with_token_override() -> None:
    result = parse_inject(Annotated[Clock, Inject(token="primary-clock")])
    assert result == ("primary-clock", False)


def test_inject_with_explicit_optional() -> None:
    result = parse_inject(Annotated[Clock, Inject(optional=True)])
    assert result == (Clock, True)


def test_inject_t_or_none_implies_optional() -> None:
    result = parse_inject(Annotated[Clock | None, Inject])
    assert result == (Clock, True)


def test_inject_t_or_none_with_explicit_optional_stays_optional() -> None:
    result = parse_inject(Annotated[Clock | None, Inject(optional=True)])
    assert result == (Clock, True)


def test_inject_token_override_with_optional() -> None:
    result = parse_inject(Annotated[Clock | None, Inject(token="weak-clock")])
    assert result == ("weak-clock", True)


def test_non_annotated_returns_none() -> None:
    assert parse_inject(Clock) is None


def test_annotated_without_inject_returns_none() -> None:
    # Some unrelated metadata, no Inject marker.
    result = parse_inject(Annotated[Clock, "documentation"])
    assert result is None


def test_inject_repr_is_descriptive() -> None:
    rep = repr(Inject(token="abc", optional=True))
    assert "token='abc'" in rep
    assert "optional=True" in rep


def test_parse_inject_params_maps_named_inject_args() -> None:
    """Walks a callable's signature, returns the ``{name: (token, optional)}`` map."""

    async def fn(
        scope: object,
        *,
        clock: Annotated[Clock, Inject],
        log: Annotated[Clock | None, Inject],
        explicit: Annotated[Clock, Inject(optional=True)],
        plain: int = 0,
    ) -> None: ...

    out = parse_inject_params(fn)
    assert set(out) == {"clock", "log", "explicit"}
    assert out["clock"] == (Clock, False)
    assert out["log"] == (Clock, True)
    assert out["explicit"] == (Clock, True)


def test_resolve_inject_kwargs_returns_resolved_dict() -> None:
    """Pull values out of a real container."""
    import asyncio

    class _Clk:
        def now(self) -> int:
            return 1

    builder = ContainerBuilder()
    builder.bind(_Clk, _Clk, lifecycle=Lifecycle.SINGLETON)
    container = builder.build()
    out = asyncio.run(resolve_inject_kwargs({"clock": (_Clk, False)}, container))
    assert isinstance(out["clock"], _Clk)


def test_resolve_inject_kwargs_optional_returns_none_on_miss() -> None:
    """Optional tokens that are unbound resolve to ``None`` instead of raising."""
    import asyncio

    container = ContainerBuilder().build()
    out = asyncio.run(resolve_inject_kwargs({"x": (Clock, True)}, container))
    assert out == {"x": None}


def test_resolve_inject_kwargs_non_optional_propagates_error() -> None:
    """Non-optional tokens that are unbound raise ``ResolutionError``."""
    import asyncio

    container = ContainerBuilder().build()
    with pytest.raises(ResolutionError):
        asyncio.run(resolve_inject_kwargs({"x": (Clock, False)}, container))


def test_resolve_inject_kwargs_no_container_raises_injection_error() -> None:
    """A ``None`` container raises ``InjectionError`` with a wiring hint."""
    import asyncio

    with pytest.raises(InjectionError) as exc_info:
        asyncio.run(resolve_inject_kwargs({"x": (Clock, False)}, None))
    assert "No container is reachable" in str(exc_info.value)


def test_injection_error_is_a_tripack_error() -> None:
    """``InjectionError`` participates in the Tripack exception hierarchy."""
    from tripack_contracts import TripackError

    assert issubclass(InjectionError, TripackError)


def test_multi_union_with_none_is_not_unwrapped() -> None:
    # ``A | B | None`` has more than one non-None member; the
    # helper leaves it untouched and the resolver gets the
    # whole union as the token (the binding would have to be
    # under that exact union, which is unusual but legal).
    class Other:
        pass

    annotation = Annotated[Clock | Other | None, Inject]
    result = parse_inject(annotation)
    assert result is not None
    token, optional = result
    # Not a single-arg unwrap, so optional stays False.
    assert optional is False
    # Token is the full union (whatever its runtime form).
    assert token == (Clock | Other | None)
