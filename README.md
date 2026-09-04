<h1 align="center">
  <img src="docs/tripack.svg" alt="Tripack" width="120" /><br/>
  Tripack
</h1>

<p align="center">
  <em>A typed IoC container for Python - sync, async, and FastAPI-ready.</em>
</p>

<p align="center">
  <a href="https://github.com/goabonga/tripack/actions/workflows/ci.yml"><img src="https://github.com/goabonga/tripack/actions/workflows/ci.yml/badge.svg?branch=main" alt="CI"/></a>
  <a href="https://codecov.io/gh/goabonga/tripack"><img src="https://img.shields.io/codecov/c/github/goabonga/tripack?logo=codecov" alt="Codecov"/></a>
  <a href="https://github.com/goabonga/tripack/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License: MIT"/></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.13%2B-blue.svg" alt="Python"/></a>
  <a href="https://github.com/astral-sh/uv"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json" alt="uv"/></a>
</p>

Tripack is a dependency-injection container for Python 3.13+, published as
three independently versioned packages: the contracts you type against, the
resolution runtime, and the container API you call.

It resolves sync and async factories through a single graph, with transient,
singleton and scoped lifecycles and deterministic teardown; composes
registrations into modules; detects dependency cycles at resolution time; and
wires an application declaratively from TOML, JSON or YAML. ASGI primitives
and a FastAPI adapter (`TripackAPI` with `Annotated[T, Inject]`) ship with
the container.

## Documentation

The project site is published from `main` to GitHub Pages:
<https://goabonga.github.io/tripack/>.

## Stability and deprecation policy

Tripack follows [Semantic Versioning](https://semver.org/) and the
standard Python `n + 2` deprecation cadence (announce + warn in one
release, remove in the release after the next). Full policy:
[`docs/stability.md`](https://github.com/goabonga/tripack/blob/main/docs/stability.md).

## Packages

The repository is a [uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/)
with three independently versioned and published packages.

| Package | Role |
| --- | --- |
| [`tripack-contracts`](https://github.com/goabonga/tripack/tree/main/packages/tripack-contracts) | Public contracts of the framework: protocols, interfaces, types, exceptions and annotations. |
| [`tripack-runtime`](https://github.com/goabonga/tripack/tree/main/packages/tripack-runtime) | Idempotent execution core: resolution, dependency graph, per-scope caching, lifecycle, validation. |
| [`tripack-container`](https://github.com/goabonga/tripack/tree/main/packages/tripack-container) | High-level IoC container API: declarations, wiring, modules, bootstrap. |

```
tripack/
├── packages/
│   ├── tripack-contracts/
│   ├── tripack-runtime/
│   └── tripack-container/
├── multicz.toml
└── pyproject.toml
```

## Requirements

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) for environment and workspace management

## Getting started

```bash
# Sync the whole workspace (creates .venv at the repo root).
uv sync --all-packages

# Run the test suite of every package.
uv run pytest

# Run the tests of a single package with coverage.
uv run --package tripack-contracts pytest --cov=tripack_contracts
```

## Versioning and release

Each package owns its version, changelog and git tag. Versions are bumped from
[Conventional Commits](https://www.conventionalcommits.org/) by
[multicz](https://github.com/goabonga/multicz), which only touches the
components whose `paths` were modified.

```bash
# Preview what would be released against the current branch.
multicz status --since origin/main

# Apply the bumps (CI does this on main).
multicz bump --commit --tag --push
```

Published artifacts (PyPI) follow the per-component version computed by
multicz.

## Contributing

See [CONTRIBUTING.md](https://github.com/goabonga/tripack/blob/main/CONTRIBUTING.md)
for the workflow, the commit-message convention, and the test/lint
expectations. By participating you agree to the
[Code of Conduct](https://github.com/goabonga/tripack/blob/main/CODE_OF_CONDUCT.md).

Security issues: please follow the disclosure process in
[SECURITY.md](https://github.com/goabonga/tripack/blob/main/SECURITY.md).

## License

Distributed under the
[MIT License](https://github.com/goabonga/tripack/blob/main/LICENSE).
