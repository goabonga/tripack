# tripack-contracts

[![PyPI](https://img.shields.io/pypi/v/tripack-contracts.svg)](https://pypi.org/project/tripack-contracts/)
[![Python](https://img.shields.io/pypi/pyversions/tripack-contracts.svg)](https://pypi.org/project/tripack-contracts/)
[![CI](https://github.com/goabonga/tripack/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/goabonga/tripack/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://github.com/goabonga/tripack/blob/main/LICENSE)

Public contracts of the [Tripack](https://github.com/goabonga/tripack) IoC
framework: protocols, interfaces, types, exceptions and annotations that
consumers and other Tripack packages depend on.

This package is the stable surface other Tripack packages and downstream
projects program against. It contains no runtime behaviour - only typing,
protocols and exceptions. Implementations live in
[`tripack-runtime`](https://github.com/goabonga/tripack/tree/main/packages/tripack-runtime)
and
[`tripack-container`](https://github.com/goabonga/tripack/tree/main/packages/tripack-container).

## Install

```bash
uv add tripack-contracts
# or
pip install tripack-contracts
```

## Documentation

Project site: <https://goabonga.github.io/tripack/>.

## License

MIT - see [LICENSE](https://github.com/goabonga/tripack/blob/main/LICENSE).
