# tripack-container

[![PyPI](https://img.shields.io/pypi/v/tripack-container.svg)](https://pypi.org/project/tripack-container/)
[![Python](https://img.shields.io/pypi/pyversions/tripack-container.svg)](https://pypi.org/project/tripack-container/)
[![CI](https://github.com/goabonga/tripack/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/goabonga/tripack/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://github.com/goabonga/tripack/blob/main/LICENSE)

High-level IoC container API of the
[Tripack](https://github.com/goabonga/tripack) framework: declarations,
wiring, modules and bootstrap helpers used by application code.

`tripack-container` is the ergonomic surface most consumers import. It is
built on top of the resolver in
[`tripack-runtime`](https://github.com/goabonga/tripack/tree/main/packages/tripack-runtime)
and the protocols defined in
[`tripack-contracts`](https://github.com/goabonga/tripack/tree/main/packages/tripack-contracts).

## Install

```bash
uv add tripack-container
# or
pip install tripack-container
```

## Documentation

Project site: <https://goabonga.github.io/tripack/>.

## License

MIT - see [LICENSE](https://github.com/goabonga/tripack/blob/main/LICENSE).
