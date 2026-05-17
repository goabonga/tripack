# Tripack

Tripack is a compact Python project exploring dependency injection and IoC
container patterns across three packages. It demonstrates clean object
wiring, decoupled services, reusable components, and maintainable
application structure.

## Packages

| Package | Role |
| --- | --- |
| [`tripack-contracts`](https://github.com/goabonga/tripack/tree/main/packages/tripack-contracts) | Public contracts of the framework: protocols, interfaces, types, exceptions and annotations. |
| [`tripack-runtime`](https://github.com/goabonga/tripack/tree/main/packages/tripack-runtime) | Idempotent execution core: resolution, dependency graph, per-scope caching, lifecycle, validation. |
| [`tripack-container`](https://github.com/goabonga/tripack/tree/main/packages/tripack-container) | High-level IoC container API: declarations, wiring, modules, bootstrap. |

See the [repository](https://github.com/goabonga/tripack) for the source,
the [release pipeline](https://github.com/goabonga/tripack/blob/main/.github/workflows/ci.yml)
and the [versioning rules](https://github.com/goabonga/tripack/blob/main/multicz.toml).
