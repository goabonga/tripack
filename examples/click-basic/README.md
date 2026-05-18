# Click integration example

A small **Click** CLI wired through a Tripack container. The
example uses the lower-level Click API directly (the layer
that Typer wraps) to show two differences from the Typer
sibling example:

- **Explicit ``@click.group()`` + ``@cli.command()``
  registration**, rather than Typer's single-decorator
  declaration.
- **``@click.pass_obj``** instead of ``click.Context.obj``
  unpacking: subcommands receive the container as their
  first positional argument, which makes the command body
  read cleanly without context-handling boilerplate.

Otherwise the integration shape is identical: build the
container under a ``with`` block, invoke the group with
``cli(obj=container)``, let the ``with`` ``__exit__`` close
the container on any program exit.

## Running

```bash
cd examples/click-basic
uv sync
uv run python -m click_basic now
uv run python -m click_basic record hello
uv run python -m click_basic record world
uv run python -m click_basic events
```

## Testing

```bash
uv run --group dev pytest
```

The tests use Click's own ``click.testing.CliRunner`` (the
same runner Typer's testing helper wraps). Three tests cover
the same scenarios as the Typer example: clock readout,
singleton-log accumulation across multiple invokes,
container isolation across two ``build_container()`` calls.

## File layout

```
src/click_basic/
├── __init__.py        # package docstring
├── __main__.py        # `python -m click_basic` entrypoint
├── services.py        # Clock / EventLog
├── wiring.py          # build_container()
└── cli.py             # click.group() + three commands with @click.pass_obj
tests/
└── test_cli.py
```

## Migrating to PyPI deps

After Tripack v0.1.0 ships, drop the ``[tool.uv.sources]``
block in ``pyproject.toml``. See ``../README.md`` for the
full migration note.
