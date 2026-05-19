# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""FastAPI adapter: ``TripackAPI`` + ``Annotated[T, Inject]``.

Layered architecture
--------------------

The Tripack injection story has three layers, each living in a
distinct module:

1. **Marker layer** (:mod:`tripack_container._inject`) -
   ``Inject`` is a pure data marker. No framework dependency.
   This is the framework-agnostic primitive every adapter
   reads.
2. **ASGI layer** (:mod:`tripack_container.asgi`) -
   :func:`container_lifespan` and
   :class:`ContainerScopeMiddleware`. Pure ASGI, no FastAPI
   import. Compatible with Starlette, FastAPI, Litestar, or a
   raw ASGI app.
3. **FastAPI adapter** (this module) - composes the ASGI
   layer and adds the FastAPI-specific concern: rewriting
   ``Annotated[T, Inject]`` to ``Annotated[T, Depends(...)]``
   on each route, so FastAPI's own dependency machinery
   resolves the token. Any other ASGI framework would write
   its own L3 adapter on the same L1+L2 foundation.

``TripackAPI`` is a **subclass** of ``FastAPI`` rather than a
composite. Trade-off:

- Subclass wins ergonomically: ``TripackAPI(...)`` looks like
  ``FastAPI(...)``, every FastAPI tool that introspects via
  ``isinstance(app, FastAPI)`` keeps working (TestClient,
  Starlette tooling, deployment patterns). Mounted apps, OAuth
  flows, ``app.dependency_overrides`` and exception handlers
  inherit through the MRO untouched.
- Composite would force ``app.fastapi`` indirection at every
  call site and break ASGI app expectations.
- Function-only would deny users the ability to subclass for
  their own concerns.

The route-class rewrite happens once per route, at
construction time. ``_TripackRoute.__init__`` walks the
endpoint's signature, finds every parameter annotated
``Annotated[T, Inject]`` (or ``Annotated[T, Inject(...)]``),
and replaces the marker with ``Depends(_factory_for(token))``.
FastAPI then sees a vanilla ``Depends(...)`` dependency and
runs it through its own resolution machinery; the body of the
dependency reads ``request.app.state.container`` (written by
:func:`container_lifespan`) and calls ``aresolve(token)``.
This keeps ``app.dependency_overrides`` usable for tests.

The lifecycle (build + close) and per-request scope are
inherited from the ASGI layer; this module composes them under
a FastAPI-shaped surface so users get a single-class import
(``TripackAPI``) without having to wire the lifespan + the
middleware themselves.
"""

from __future__ import annotations

import inspect
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import TYPE_CHECKING, Annotated, Any, cast, get_args

# FastAPI is a peer dependency of the ``[fastapi]`` extra; if
# the user reaches this module without installing the extra
# the standard ``ModuleNotFoundError: No module named 'fastapi'``
# fires here with a clear traceback pointing at this line.
# Wrapping the import in ``try/except`` to attach a custom hint
# would push the failure outside the coverage gate without
# adding actionable information beyond what pip / uv already
# print when an extra is missing.
from fastapi import Depends, FastAPI, Request
from fastapi.routing import APIRoute, APIRouter

from tripack_container._inject import parse_inject
from tripack_container.asgi import (
    ContainerFactory,
    ContainerScopeMiddleware,
    container_lifespan,
)
from tripack_contracts import ResolutionError

if TYPE_CHECKING:
    from tripack_container.container import Container


class TripackAPI(FastAPI):
    """FastAPI with built-in container lifecycle and ``Inject`` resolution.

    Pass a ``container_factory`` to the constructor; the rest
    is wired automatically:

    - the container is built (sync or async factory both work)
      at lifespan startup and ``aclose``d at shutdown;
    - every HTTP request runs inside ``container.ascope()`` so
      SCOPED bindings cache per-request;
    - route parameters annotated ``Annotated[T, Inject]`` are
      rewritten at registration time so FastAPI's own
      dependency system resolves ``T`` from the container.

    Sub-routers attached via ``include_router`` inherit the
    inject-aware route class automatically (only if they kept
    the default ``APIRoute``; a router with a custom route_class
    is left untouched).
    """

    def __init__(
        self,
        *args: Any,
        container_factory: ContainerFactory,
        **kwargs: Any,
    ) -> None:
        """Wire ASGI lifespan + scope middleware + route_class around FastAPI.

        Both the lifespan composition and the per-request scope
        come from :mod:`tripack_container.asgi` - this class only
        adds the FastAPI-specific route-class swap. A Starlette
        adapter would do exactly the same thing minus the
        ``route_class`` (because Starlette has no ``Depends``
        machinery to feed the rewritten annotation into).
        """
        user_lifespan = kwargs.pop("lifespan", None)
        kwargs["lifespan"] = _compose_lifespan(container_factory, user_lifespan)
        super().__init__(*args, **kwargs)
        self.router.route_class = _TripackRoute
        self.add_middleware(ContainerScopeMiddleware)

    def include_router(self, router: APIRouter, *args: Any, **kwargs: Any) -> None:
        """Forward the inject-aware route class to default sub-routers.

        Re-emits a warning-free include for routers built with
        :class:`TripackRouter` (whose ``route_class`` already
        matches) and tags vanilla ``APIRouter`` instances so a
        later ``add_api_route`` call inherits the rewriting.
        Routes already registered on a plain :class:`APIRouter`
        will **not** be retroactively rewritten - by the time
        ``@sub.get`` ran, FastAPI had already analysed the
        endpoint. For sub-routers that use ``Inject``, instantiate
        :class:`TripackRouter` instead of :class:`APIRouter`.
        """
        if router.route_class is APIRoute:
            router.route_class = _TripackRoute
        super().include_router(router, *args, **kwargs)


class TripackRouter(APIRouter):
    """``APIRouter`` that defaults to the inject-aware route class.

    Use in place of :class:`APIRouter` when sub-router endpoints
    declare ``Annotated[T, Inject]`` parameters:

    ```python
    sub = TripackRouter(prefix="/v2")

    @sub.get("/now")
    def now(clock: Annotated[Clock, Inject]) -> dict[str, int]:
        return {"now": clock.now()}

    app.include_router(sub)
    ```

    The default :class:`APIRouter` would crash at ``@sub.get``
    time because FastAPI introspects the endpoint at route
    registration and rejects the bare ``Inject`` marker as a
    non-Pydantic field. :class:`TripackRouter` rewrites the
    annotation before FastAPI sees it - the same mechanism
    :class:`TripackAPI` uses for top-level routes.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Default ``route_class`` to the inject-aware variant."""
        kwargs.setdefault("route_class", _TripackRoute)
        super().__init__(*args, **kwargs)


_LifespanFactory = Callable[[FastAPI], AbstractAsyncContextManager[None]]


def _compose_lifespan(
    factory: ContainerFactory,
    user_lifespan: _LifespanFactory | None,
) -> _LifespanFactory:
    """Layer the user's lifespan inside :func:`container_lifespan`.

    Pure composition: the container is built first (so the user
    lifespan can read ``app.state.container``), and ``aclose``
    runs last (so the user teardown still reaches the container).
    """

    @asynccontextmanager
    async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with container_lifespan(app, container_factory=factory):
            if user_lifespan is None:
                yield
            else:
                async with user_lifespan(app):
                    yield

    return _lifespan


class _TripackRoute(APIRoute):
    """``APIRoute`` that rewrites ``Annotated[T, Inject]`` to ``Depends``.

    Walking the endpoint signature at construction time keeps
    the rewrite cost off the request path. Once FastAPI builds
    the route from the rewritten signature, the inject sites
    are plain ``Annotated[T, Depends(...)]`` - the same shape
    FastAPI handles natively.
    """

    def __init__(self, path: str, endpoint: Callable[..., Any], **kwargs: Any) -> None:
        """Rewrite the endpoint's signature before delegating to FastAPI."""
        super().__init__(path, _rewrite_endpoint(endpoint), **kwargs)


def _rewrite_endpoint(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Replace each ``Annotated[T, Inject]`` param with ``Annotated[T, Depends(...)]``.

    Mutates the function's ``__signature__`` so FastAPI sees
    the rewritten annotations during route introspection. The
    underlying callable is returned untouched - only its
    metadata changes. The original signature is preserved on
    ``__wrapped__`` is **not** set: FastAPI uses
    ``inspect.signature`` which prefers ``__signature__`` when
    set.
    """
    sig = inspect.signature(fn)
    hints = inspect.get_annotations(fn, eval_str=True)
    new_params: list[inspect.Parameter] = []
    rewritten = False
    for name, param in sig.parameters.items():
        annotation = hints.get(name, param.annotation)
        parsed = parse_inject(annotation)
        if parsed is None:
            new_params.append(param)
            continue
        token, optional = parsed
        # Preserve the original ``T`` (with ``| None`` if present)
        # in the rewritten annotation so FastAPI's response
        # model inference and downstream type tooling keep
        # seeing the user-facing type rather than ``Any``. The
        # ``cast`` keeps mypy quiet about a runtime-built
        # ``Annotated[...]`` (variable substitution into a type
        # form is intentionally not statically checkable).
        original_typed = get_args(annotation)[0]
        depends = Depends(_make_dependency(token, optional=optional))
        new_annotation = cast("Any", Annotated[(original_typed, depends)])
        new_params.append(param.replace(annotation=new_annotation))
        rewritten = True
    if rewritten:
        fn.__signature__ = sig.replace(parameters=new_params)  # type: ignore[attr-defined]
    return fn


def _make_dependency(
    token: object, *, optional: bool
) -> Callable[[Request], Awaitable[Any]]:
    """Build the ``Depends`` callable that resolves ``token`` per request.

    The returned coroutine is what FastAPI registers as a
    dependency. It reads the container off the request, awaits
    ``aresolve`` (which handles both sync and async factories
    uniformly), and translates a missing-binding error to
    ``None`` when ``optional=True``.
    """

    async def _dep(request: Request) -> Any:
        container = cast("Container", request.app.state.container)
        try:
            return await container.aresolve(cast("type[Any]", token))
        except ResolutionError:
            if optional:
                return None
            raise

    return _dep
