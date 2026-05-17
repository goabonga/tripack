# Exception hierarchy

Every error the framework raises is a subclass of `TripackError`,
so consumers can catch the entire surface in one clause:

```python
from tripack_contracts import TripackError

try:
    container.resolve(Clock)
except TripackError:
    # any Tripack failure: resolution, binding, scope, config, cycle
    ...
```

The hierarchy is intentionally shallow so the matrix of "what to
catch" is short to memorise:

```
TripackError                 (base)
├── ResolutionError          token cannot be resolved
│   └── CircularDependencyError    cycle detected during resolution
├── BindingError             binding registration failure / conflict
├── ScopeError               scope unknown or expired
└── ConfigurationError       declarative config invalid / unloadable
```

## When each one fires

| Class | Raised when |
| --- | --- |
| `TripackError` | base class - never raised directly by the framework. Consumers MAY catch it to handle "any framework error". |
| `ResolutionError` | the runtime cannot resolve a token (no binding, or the binding's factory raised). |
| `CircularDependencyError` | resolution detected a cycle in the dependency graph. Subclass of `ResolutionError`. |
| `BindingError` | a binding cannot be registered: duplicate token with a different factory or lifecycle, or factory signature incompatible with the declared lifecycle. |
| `ScopeError` | resolving a `SCOPED` binding outside of any scope, or using a scope reference whose context manager has already exited. |
| `ConfigurationError` | TOML / JSON / YAML configuration is malformed, schema-invalid, or references a callable that cannot be imported. |

## Catching strategy

```python
# Coarse: handle anything Tripack-related uniformly.
try:
    ...
except TripackError:
    ...

# Mid: distinguish setup-time from resolution-time errors.
try:
    ...
except BindingError:
    # bad registration - bug at startup
    ...
except ResolutionError:
    # missing binding or cycle - bug in wiring
    ...

# Fine: dedicated path for cycles.
try:
    ...
except CircularDependencyError as exc:
    cycle = " -> ".join(t.__qualname__ for t in exc.cycle if isinstance(t, type))
    log.error("cycle: %s", cycle)
```

## `CircularDependencyError` carries the cycle

This is the only subclass with attached state. The `cycle` attribute
is a `tuple[DependencyToken, ...]` describing the loop, where by
convention the first and last entries are the same token:

```python
from tripack_contracts import CircularDependencyError


err = CircularDependencyError([Clock, Cache, Clock])
err.cycle              # (<class 'Clock'>, <class 'Cache'>, <class 'Clock'>)
str(err)               # "Circular dependency detected: Clock -> Cache -> Clock"
```

Class tokens render as `__qualname__` in the formatted message;
non-class tokens (strings, tuples) fall back to `repr`.

## All errors are picklable

Every class in the hierarchy round-trips through `pickle`, including
`CircularDependencyError` which uses a custom `__reduce__` to
preserve the `cycle` tuple on the unpickled instance:

```python
import pickle

from tripack_contracts import CircularDependencyError


err = CircularDependencyError(["a", "b", "a"])
revived = pickle.loads(pickle.dumps(err))
assert revived.cycle == ("a", "b", "a")
```

This matters for multiprocess workers, traceback serialisation, and
test fixtures that snapshot exceptions.
