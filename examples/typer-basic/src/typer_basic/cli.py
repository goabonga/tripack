# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Typer commands: receive the container via ``typer.Context.obj``.

The CLI follows the canonical Typer / Click pattern: a
:class:`typer.Context` is threaded through every command, the
container hangs off ``ctx.obj``, and each handler calls
:meth:`Container.resolve` to fetch what it needs.

The container is built once at the entrypoint (see
:mod:`typer_basic.__main__`) and torn down on CLI exit so the
SINGLETON ``EventLog`` survives across every ``record`` /
``events`` call within one invocation.
"""

import typer

from tripack_container import Container
from typer_basic.services import Clock, EventLog

app = typer.Typer(
    name="tripack-example-typer",
    help="Tripack + Typer integration example.",
    no_args_is_help=True,
)


def _container(ctx: typer.Context) -> Container:
    """Pull the container off the Click context.

    The entrypoint hands the container in via ``app(obj=...)``,
    which Click stores on ``ctx.obj``; this helper hides the
    cast so the command bodies read cleanly.
    """
    container: Container = ctx.obj
    return container


@app.command()
def now(ctx: typer.Context) -> None:
    """Print the current SINGLETON :class:`Clock` reading."""
    clock = _container(ctx).resolve(Clock)
    typer.echo(f"now = {clock.now()}")


@app.command()
def record(
    ctx: typer.Context,
    message: str = typer.Argument(..., help="The message to append to the log."),
) -> None:
    """Append ``message`` to the SINGLETON event log."""
    container = _container(ctx)
    clock = container.resolve(Clock)
    log = container.resolve(EventLog)
    log.record(clock.now(), message)
    typer.echo(f"recorded ({len(log.all())} entries total)")


@app.command()
def events(ctx: typer.Context) -> None:
    """List every entry recorded so far."""
    log = _container(ctx).resolve(EventLog)
    for when, message in log.all():
        typer.echo(f"{when:.3f}  {message}")
