# Configuration: TOML loader

`Container.from_toml(path)` loads a sealed `Container` from a
TOML configuration file. Tokens, factories, and modules are
named through dotted Python paths that the loader resolves via
`importlib.import_module` plus `getattr`, so the wiring lives
entirely in declarative text - the application code is just the
objects pointed at.

```toml
modules = ["my_app.modules.CacheModule"]

[[bindings]]
token = "my_app.services.Clock"
factory = "my_app.factories.make_clock"
lifecycle = "singleton"

[[bindings]]
token = "my_app.services.Session"
factory = "my_app.factories.make_session_async"
lifecycle = "scoped"
async_factory = true

[[bindings]]
token = "my_app.services.App"
factory = "my_app.factories.make_app"
lifecycle = "transient"
auto_inject = true
```

```python
from tripack_container import Container

container = Container.from_toml("config.toml")
```

## Validation

Every loader validates the parsed dict against the
`ContainerConfig` TypedDict shape before any binding hits the
builder, so a structurally invalid file raises
`ConfigurationError` without producing a half-wired container.
The validator checks:

- The top-level value is a table / object.
- A `bindings` key exists and is a list.
- Each binding has `token`, `factory`, `lifecycle` keys.
- `token` and `factory` are strings.
- `lifecycle` is one of `"transient"`, `"singleton"`, `"scoped"`.
- The optional `async_factory` and `auto_inject` flags are bools.
- The optional `modules` key is a list of strings.

## Imports

Tokens and factories are resolved at load time. Both the
"unknown module" and "missing attribute" cases surface as a
single `ConfigurationError` with a clear message, so consumers
can catch one exception type for every kind of declarative
failure.

A name without a dot is rejected on principle: the loader needs
the module path to call `importlib.import_module`. A bare
identifier (`"Clock"`) raises `ConfigurationError` rather than
silently failing.

## Modules

The optional `modules = [...]` array names `Module`-shaped
classes (or already-instantiated module instances). For each
qualified name, the loader imports it; if it resolves to a
class, it instantiates with no args; then it calls
`builder.install` on the result. A name that does not resolve
to something with a callable `register` method is rejected at
load time.

## Why TOML?

TOML lives in the standard library since Python 3.11 via
`tomllib`, so the TOML loader adds **zero** runtime
dependency. It is the recommended format for application
configuration in modern Python and the most natural fit for
`pyproject.toml`-adjacent ecosystems.

The JSON loader (4.10) is parser-equivalent and also has zero
new dependency. The YAML loader (4.11) requires the optional
`tripack-container[yaml]` extra.
