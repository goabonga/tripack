# Configuration: JSON loader

`Container.from_json(path)` is the JSON counterpart of
[`from_toml`](config-toml.md). It uses the standard-library
`json` module (no extra runtime dependency) and shares the
same validation pipeline, the same `ContainerConfig` schema,
and the same `importlib`-based qualified-name resolution.

```json
{
  "modules": ["my_app.modules.CacheModule"],
  "bindings": [
    {
      "token": "my_app.services.Clock",
      "factory": "my_app.factories.make_clock",
      "lifecycle": "singleton"
    },
    {
      "token": "my_app.services.Session",
      "factory": "my_app.factories.make_session_async",
      "lifecycle": "scoped",
      "async_factory": true
    },
    {
      "token": "my_app.services.App",
      "factory": "my_app.factories.make_app",
      "lifecycle": "transient",
      "auto_inject": true
    }
  ]
}
```

```python
from tripack_container import Container

container = Container.from_json("config.json")
```

## Decoding errors

A malformed JSON file surfaces as `ConfigurationError` with the
decoder's message attached. Consumers can catch a single
exception type for every kind of declarative failure, parser
included:

```python
try:
    Container.from_json("broken.json")
except ConfigurationError as exc:
    log.error("config rejected: %s", exc)
```

The underlying `json.JSONDecodeError` is wrapped, not exposed.

## Why JSON?

JSON is universal: every editor, every CI pipeline, every
serialization layer speaks it. It is the natural fit when the
container's wiring is produced by another tool (a code
generator, an orchestrator, a UI), and it lives well alongside
TOML (`config-toml.md`) for human-authored cases.

For human-authored configuration on developer machines, prefer
TOML; for machine-generated or interchange-formatted
configuration, prefer JSON.

## Schema parity

The JSON schema is identical to the TOML schema; only the
serialization format differs. Switching between the two is a
file conversion away. The TOML examples in
[`config-toml.md`](config-toml.md) translate directly: each
`[[bindings]]` table becomes one object in the JSON `bindings`
array, `modules = [...]` becomes a `"modules": [...]` array,
and the optional flags carry the same names and types.
