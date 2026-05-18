# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Click command group: container delivered via ``@click.pass_obj``.

``@click.pass_obj`` is Click's shortcut decorator that passes
``ctx.obj`` as the first positional argument of the wrapped
function (instead of the full :class:`click.Context`). For a
CLI whose context object IS the container, this is the
cleanest way to write commands: the body reads
``container.resolve(...)`` directly without unpacking
machinery.

The container is populated onto ``ctx.obj`` by the entrypoint
that invokes the group as ``cli(obj=container)`` (see
:mod:`click_basic.__main__`).
"""

import click

from click_basic.services import Clock, EventLog
from tripack_container import Container


@click.group(
    name="tripack-example-click",
    help="Tripack + Click integration example.",
)
def cli() -> None:
    """Root group; subcommands receive the container via ``@click.pass_obj``."""


@cli.command()
@click.pass_obj
def now(container: Container) -> None:
    """Print the SINGLETON :class:`Clock` reading."""
    clock = container.resolve(Clock)
    click.echo(f"now = {clock.now()}")


@cli.command()
@click.argument("message")
@click.pass_obj
def record(container: Container, message: str) -> None:
    """Append ``MESSAGE`` to the SINGLETON event log."""
    clock = container.resolve(Clock)
    log = container.resolve(EventLog)
    log.record(clock.now(), message)
    click.echo(f"recorded ({len(log.all())} entries total)")


@cli.command()
@click.pass_obj
def events(container: Container) -> None:
    """List every entry recorded so far."""
    log = container.resolve(EventLog)
    for when, message in log.all():
        click.echo(f"{when:.3f}  {message}")
