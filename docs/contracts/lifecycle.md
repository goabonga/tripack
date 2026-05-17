# Lifecycle

A `Lifecycle` decides how many times a binding's factory is invoked
and how long the resulting instance is cached. Pick the lifecycle at
registration time; the runtime enforces the corresponding caching
policy on every resolution.

```python
from tripack_contracts import Lifecycle
```

## The three values

### `Lifecycle.TRANSIENT`

> A fresh instance is produced on every resolution.

Idempotency promise: the **resolver call is deterministic** but the
**instance is not cached**. Calling `container.resolve(Clock)` twice
calls the factory twice and returns two distinct instances.

Use for:

- Stateless utilities whose construction is cheap.
- Objects that intentionally must not be shared (e.g., a builder
  pattern whose state is consumed during use).

Avoid for:

- Expensive constructors (database clients, HTTP sessions).
- Objects that hold a closeable resource - they would never be
  closed by the framework because the container does not retain
  them.

### `Lifecycle.SINGLETON`

> One instance per container, cached after first resolution.

Idempotency promise: **same container + same token = same instance**,
forever. The factory runs **exactly once** for a given container, even
under concurrent resolution. If the factory raises, the cache stays
empty - the next call gets another shot rather than being poisoned
by the previous failure.

Use for:

- Application-wide stateful services (`Clock`, `Logger`, `Cache`).
- Resources backed by `Closeable` / `AsyncCloseable` - the runtime
  tracks them automatically and closes them when the container does.

Avoid for:

- Anything that holds request-scoped state (correlation IDs, tenant
  configuration) - use `SCOPED` instead.

### `Lifecycle.SCOPED`

> One instance per `Scope`, cached within that scope.

Idempotency promise: **same scope + same token = same instance**;
**different scopes = different instances**. The factory runs once per
scope. When the scope exits its context manager, the runtime closes
every `Closeable` it produced.

Use for:

- Request-scoped state in a web app (current user, db transaction).
- Test-scoped fixtures that must be isolated between test cases.

Avoid for:

- Long-lived state that should outlast the scope - prefer
  `SINGLETON`.

## Type definition

```python
from enum import StrEnum


class Lifecycle(StrEnum):
    TRANSIENT = "transient"
    SINGLETON = "singleton"
    SCOPED = "scoped"
```

The class is a [`StrEnum`](https://docs.python.org/3/library/enum.html#enum.StrEnum),
which means members compare equal to their bare string value and
serialise cleanly through configuration loaders (TOML / JSON / YAML)
without any custom encoder.

## Comparison cheat sheet

| Lifecycle | Factory runs | Cached in | Teardown owner |
| --- | --- | --- | --- |
| `TRANSIENT` | every resolve | nowhere | caller (the framework does not retain a reference) |
| `SINGLETON` | once per container | the container | the container, on `close()` / `aclose()` |
| `SCOPED` | once per scope | the scope | the scope, on context-manager exit |
