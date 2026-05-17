# Dependency tokens

A `DependencyToken` is the key under which the container looks up a
binding. Tripack accepts three flavours of tokens, in decreasing
order of expected usage:

1. **A class** - the canonical case. The type the consumer declares
   as a dependency *is* the lookup key, so the resolver returns an
   instance of that class without any indirection.
2. **A string** - named binding pattern. Useful when there is no
   natural class to use as the key, or when you need multiple
   instances of the same class registered under different names.
3. **Any other hashable value** - composite tokens. Typically tuples,
   for cases where string concatenation feels brittle (`("clock",
   "primary")` beats `"clock-primary"`).

## Type definition

```python
from collections.abc import Hashable
from typing import Any

type DependencyToken = type[Any] | str | Hashable
```

The alias is declared with the PEP 695 `type` statement (Python
3.13+), which makes it a real `TypeAliasType` at runtime - inspectable
via `DependencyToken.__name__`, `DependencyToken.__value__`, etc.

## Examples

```python
from tripack_contracts import DependencyToken


# 1. Class as token (most common).
class Clock: ...


clock_token: DependencyToken = Clock

# 2. String as token (named binding).
primary_clock: DependencyToken = "primary-clock"
secondary_clock: DependencyToken = "secondary-clock"

# 3. Composite hashable token.
namespaced: DependencyToken = ("clock", "primary")
```

## When to use which

| Token kind | Use it for |
| --- | --- |
| Class | Most bindings. The type *is* the lookup key. `mypy` gives you full type inference at the call site. |
| String | When there is no obvious class, or when you need several named instances of the same class (e.g., `"primary-clock"` and `"secondary-clock"` both of class `Clock`). |
| Hashable tuple | Composite naming when string concatenation feels brittle - prefer tuples so each segment stays a first-class value. |

## What is NOT a token

- Mutable values (lists, dicts) are not hashable and rejected at
  registration time by the runtime registry.
- `None` is technically hashable but never resolves to a useful
  binding; the runtime rejects it explicitly to catch accidental
  misuse.
