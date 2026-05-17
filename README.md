# Tripack

[![CI](https://github.com/goabonga/tripack/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/goabonga/tripack/actions/workflows/ci.yml)
[![Codecov](https://img.shields.io/codecov/c/github/goabonga/tripack?logo=codecov)](https://codecov.io/gh/goabonga/tripack)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://github.com/goabonga/tripack/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/python-3.13%2B-blue.svg)](https://www.python.org/downloads/)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)

Tripack is a compact Python project exploring dependency injection and IoC
container patterns across three packages. It demonstrates clean object wiring,
decoupled services, reusable components, and maintainable application
structure.

## Documentation

The project site is published from `main` to GitHub Pages:
<https://goabonga.github.io/tripack/>.

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
