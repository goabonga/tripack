# tripack-runtime

[![PyPI](https://img.shields.io/pypi/v/tripack-runtime.svg)](https://pypi.org/project/tripack-runtime/)
[![Python](https://img.shields.io/pypi/pyversions/tripack-runtime.svg)](https://pypi.org/project/tripack-runtime/)
[![CI](https://github.com/goabonga/tripack/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/goabonga/tripack/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://github.com/goabonga/tripack/blob/main/LICENSE)

Idempotent execution core of the [Tripack](https://github.com/goabonga/tripack)
IoC framework: resolution engine, dependency graph, per-scope caching,
lifecycle management and validation.

`tripack-runtime` consumes the contracts published by
[`tripack-contracts`](https://github.com/goabonga/tripack/tree/main/packages/tripack-contracts)
and is consumed by the high-level API in
[`tripack-container`](https://github.com/goabonga/tripack/tree/main/packages/tripack-container).

## Install

```bash
uv add tripack-runtime
# or
pip install tripack-runtime
```

## License

MIT - see [LICENSE](https://github.com/goabonga/tripack/blob/main/LICENSE).
