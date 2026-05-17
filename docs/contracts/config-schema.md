# Declarative configuration schema

`BindingSpec` and `ContainerConfig` are the two `TypedDict` types
that describe the shape of a Tripack container configuration as it
is read from a TOML, JSON or YAML file. The loaders that consume
them live in `tripack-container`; this schema is the public contract
between the file format and the runtime.

```python
from tripack_contracts import BindingSpec, ContainerConfig
```

## Why TypedDict, not dataclass

- `TypedDict` describes a **dict** shape exactly: what TOML / JSON /
  YAML deserialise into natively. No conversion layer required
  between parsing and validation.
- mypy strict checks key presence and value types at the call site,
  so configuration files that are constructed in Python (test
  fixtures, migrations) are type-checked end-to-end.
- The cost: TypedDicts have **no runtime validation**. Loaders are
  responsible for raising
  [`ConfigurationError`](errors.md) on malformed input. This
  separation keeps `tripack-contracts` dependency-free.

## `BindingSpec`

One entry under the top-level `bindings` list.

```python
class BindingSpec(TypedDict):
    token: str
    factory: str
    lifecycle: Literal["transient", "singleton", "scoped"]
    async_factory: NotRequired[bool]
    auto_inject: NotRequired[bool]
```

### Field-by-field

| Field | Required | Description |
| --- | --- | --- |
| `token` | yes | Qualified dotted name of the token class (`my_app.contracts.Clock`) or an arbitrary string alias (`"primary-clock"`). |
| `factory` | yes | Qualified dotted name of the callable that produces the bound instance. The loader resolves this with `importlib`. |
| `lifecycle` | yes | One of the three [`Lifecycle`](lifecycle.md) string values. |
| `async_factory` | no (default `False`) | `True` when the factory is a coroutine (`async def`). The runtime calls it via `await`. |
| `auto_inject` | no (default `False`) | `True` to request automatic constructor injection on the factory's parameters. See the constructor-injection doc in the container package. |

### Minimal example

```python
spec: BindingSpec = {
    "token": "my_app.contracts.Clock",
    "factory": "my_app.factories.system_clock",
    "lifecycle": "singleton",
}
```

### Full example

```python
spec: BindingSpec = {
    "token": "my_app.contracts.AsyncDb",
    "factory": "my_app.factories.async_db",
    "lifecycle": "singleton",
    "async_factory": True,
    "auto_inject": True,
}
```

## `ContainerConfig`

The root document.

```python
class ContainerConfig(TypedDict):
    bindings: list[BindingSpec]
    modules: NotRequired[list[str]]
```

### Field-by-field

| Field | Required | Description |
| --- | --- | --- |
| `bindings` | yes | Ordered list of `BindingSpec`. May be empty, but the key itself must be present so the loader can distinguish "empty container" from "malformed file". |
| `modules` | no | List of qualified module names. Each module's `register(builder)` callable is invoked before bindings are applied, so module-defined tokens can be overridden by explicit `[[bindings]]` entries. |

### Realistic example

```python
config: ContainerConfig = {
    "bindings": [
        {
            "token": "my_app.contracts.Clock",
            "factory": "my_app.factories.system_clock",
            "lifecycle": "singleton",
        },
        {
            "token": "my_app.contracts.Cache",
            "factory": "my_app.factories.memory_cache",
            "lifecycle": "scoped",
            "auto_inject": True,
        },
        {
            "token": "my_app.contracts.AsyncDb",
            "factory": "my_app.factories.async_db",
            "lifecycle": "singleton",
            "async_factory": True,
            "auto_inject": True,
        },
    ],
    "modules": ["my_app.modules.persistence"],
}
```

## Equivalent TOML

The same configuration rendered as TOML (the canonical file format):

```toml
[[bindings]]
token = "my_app.contracts.Clock"
factory = "my_app.factories.system_clock"
lifecycle = "singleton"

[[bindings]]
token = "my_app.contracts.Cache"
factory = "my_app.factories.memory_cache"
lifecycle = "scoped"
auto_inject = true

[[bindings]]
token = "my_app.contracts.AsyncDb"
factory = "my_app.factories.async_db"
lifecycle = "singleton"
async_factory = true
auto_inject = true

modules = ["my_app.modules.persistence"]
```

JSON and YAML loaders accept structurally identical input.

## Introspecting required vs optional keys

The TypedDicts carry the metadata on themselves:

```python
BindingSpec.__required_keys__
# frozenset({'token', 'factory', 'lifecycle'})

BindingSpec.__optional_keys__
# frozenset({'async_factory', 'auto_inject'})

ContainerConfig.__required_keys__
# frozenset({'bindings'})

ContainerConfig.__optional_keys__
# frozenset({'modules'})
```

This is what the loaders use internally to validate parsed
dictionaries before passing them to the container builder.
