# Typer integration example

A small **Typer** CLI wired through a Tripack container. The
example shows how a CLI process bootstraps a container at
startup, threads it through every Typer command via
``typer.Context.obj``, and tears it down on exit.

## What it shows

- **Single-process bootstrap**: the entrypoint builds the
  container under a ``with`` block; Typer / Click runs
  inside the block; the ``__exit__`` of the ``with`` fires
  even on the ``SystemExit`` that Typer raises on a non-zero
  exit code, so the container's ``close`` always runs.
- **Container-via-context**: the entrypoint calls
  ``app(obj=container)``. Click stores ``obj`` on the
  ``typer.Context`` of every command, where the ``_container``
  helper unpacks it. Commands then resolve services via the
  container exactly as they would in any other Tripack
  consumer.
- **Container persistence across commands**: SINGLETON
  bindings cache across multiple CLI invocations **within
  one process**. The CLI runs one command and exits, so for a
  one-shot CLI SINGLETON behaves the same as TRANSIENT - the
  interesting case is the test suite, which keeps the
  container alive across several ``CliRunner.invoke`` calls.

## Running

```bash
cd examples/typer-basic
uv sync
uv run python -m typer_basic now
uv run python -m typer_basic record hello
uv run python -m typer_basic record world
uv run python -m typer_basic events
```

## Testing

```bash
uv run --group dev pytest
```

The tests reuse one container across multiple ``invoke``
calls to demonstrate SINGLETON state surviving across
commands. They also build a second container in isolation to
show that two containers do not share state.

## File layout

```
src/typer_basic/
├── __init__.py        # package docstring
├── __main__.py        # `python -m typer_basic` entrypoint
├── services.py        # Clock / EventLog
├── wiring.py          # build_container()
└── cli.py             # typer.Typer() + three commands
tests/
└── test_cli.py
```
