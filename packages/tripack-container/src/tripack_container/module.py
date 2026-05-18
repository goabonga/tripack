# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Module protocol - reusable bundles of bindings.

A :class:`Module` is a small object that knows how to register
a coherent slice of the wiring onto a
:class:`ContainerBuilder`. Modules are the unit of composition
above raw ``bind`` calls: a feature, a subsystem, or an
infrastructure adapter can ship one and have its consumer
``install`` it from a single line. Multiple modules combine
freely, and a module can install other modules to express
composition.

```python
class CacheModule:
    def register(self, builder: ContainerBuilder) -> None:
        builder.bind(Cache, make_cache, lifecycle=Lifecycle.SINGLETON)
        builder.bind(CacheConfig, make_cache_config)


class AppModule:
    def register(self, builder: ContainerBuilder) -> None:
        # Compose by installing a sub-module first.
        builder.install(CacheModule())
        builder.bind(App, make_app)


container = ContainerBuilder().install(AppModule()).build()
```

The Protocol is structural: any object that exposes the
``register`` method qualifies, without inheritance. The body
raises :class:`NotImplementedError` defensively so a direct
invocation on the Protocol class fails loud instead of
silently returning ``None``.
"""

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from tripack_container.builder import ContainerBuilder


class Module(Protocol):
    """A reusable bundle of bindings.

    A class satisfies :class:`Module` iff it exposes a single
    method ``register(builder: ContainerBuilder) -> None``.
    The method is called once per
    :meth:`ContainerBuilder.install` (subject to the
    builder's per-instance idempotence guard).
    """

    def register(self, builder: "ContainerBuilder") -> None:
        """Apply this module's bindings to ``builder``.

        Implementations call :meth:`ContainerBuilder.bind` for
        each token they own, or :meth:`ContainerBuilder.install`
        to compose with another :class:`Module`.
        """
        raise NotImplementedError
