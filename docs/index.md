# Tripack

Tripack is a dependency-injection container for Python 3.13+, published as
three independently versioned packages: the contracts you type against, the
resolution runtime, and the container API you call.

It resolves sync and async factories through a single graph, with transient,
singleton and scoped lifecycles and deterministic teardown; composes
registrations into modules; detects dependency cycles at resolution time; and
wires an application declaratively from TOML, JSON or YAML. ASGI primitives
and a FastAPI adapter (`TripackAPI` with `Annotated[T, Inject]`) ship with
the container.

## Packages

| Package | Role |
| --- | --- |
| [`tripack-contracts`](https://github.com/goabonga/tripack/tree/main/packages/tripack-contracts) | Public contracts of the framework: protocols, interfaces, types, exceptions and annotations. |
| [`tripack-runtime`](https://github.com/goabonga/tripack/tree/main/packages/tripack-runtime) | Idempotent execution core: resolution, dependency graph, per-scope caching, lifecycle, validation. |
| [`tripack-container`](https://github.com/goabonga/tripack/tree/main/packages/tripack-container) | High-level IoC container API: declarations, wiring, modules, bootstrap. |

See the [repository](https://github.com/goabonga/tripack) for the source,
the [release pipeline](https://github.com/goabonga/tripack/blob/main/.github/workflows/ci.yml)
and the [versioning rules](https://github.com/goabonga/tripack/blob/main/multicz.toml).
