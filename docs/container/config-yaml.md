# Configuration: YAML loader

`Container.from_yaml(path)` is the YAML counterpart of
[`from_toml`](config-toml.md) and [`from_json`](config-json.md).
Unlike the TOML and JSON loaders, it requires the optional
`yaml` extra which pulls in [PyYAML](https://pyyaml.org/):

```bash
pip install tripack-container[yaml]
```

Without the extra, the call raises `ConfigurationError`
pointing at this install command rather than the bare
`ModuleNotFoundError`.

```yaml
modules:
  - my_app.modules.CacheModule

bindings:
  - token: my_app.services.Clock
    factory: my_app.factories.make_clock
    lifecycle: singleton

  - token: my_app.services.Session
    factory: my_app.factories.make_session_async
    lifecycle: scoped
    async_factory: true

  - token: my_app.services.App
    factory: my_app.factories.make_app
    lifecycle: transient
    auto_inject: true
```

```python
from tripack_container import Container

container = Container.from_yaml("config.yaml")
```

## Parser safety

The loader uses `yaml.safe_load`, which only parses the standard
YAML scalar / mapping / sequence types. It will NOT instantiate
arbitrary Python objects from `!!python/object` tags, so a
malicious config file cannot use the loader as a remote-code-
execution vector. This is the right default for declarative
wiring; users that genuinely need full-loader behavior should
parse the file themselves and call
`Container.from_dict`-style helpers (not provided in this
release).

## Schema parity

The YAML schema is identical to the TOML and JSON ones; only
the serialization format differs. Each `[[bindings]]` table
becomes one entry in the YAML `bindings:` sequence, and the
optional flags carry the same names and types.

## Errors

- **Missing extra**: `pip install tripack-container[yaml]`
  required; `ConfigurationError` with an install hint.
- **Malformed YAML**: `yaml.YAMLError` wrapped into
  `ConfigurationError` with the parser's message attached.
- **Invalid structure / unknown lifecycle / non-importable
  factory**: same errors as TOML / JSON, since validation runs
  through the shared `build_container_from_config` helper.

## Why an optional dependency?

TOML and JSON are in the standard library (3.11+); adding
PyYAML as a hard dependency would bloat the install footprint
for users who do not need YAML. The optional extra keeps the
core `tripack-container` install small and lets YAML users
opt in.
