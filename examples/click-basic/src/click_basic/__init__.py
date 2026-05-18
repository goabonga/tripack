# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Tripack + Click integration example.

A CLI built on plain Click (the layer that Typer wraps).
Demonstrates the Click-idiomatic pattern for handing a
container to subcommands:

- the entrypoint builds the container under a ``with`` block
  and invokes the Click group with ``cli(obj=container)``;
- subcommands use ``@click.pass_obj`` so they receive the
  container as their first positional argument, without
  having to unpack ``ctx.obj`` manually.

This is intentionally different from the Typer example
(``examples/typer-basic/`` uses ``ctx.obj`` directly so the
pattern is visible end-to-end): same problem, two flavors of
the same Click feature.

Commands:

- ``now``    - print the SINGLETON :class:`Clock` reading.
- ``record`` - append a message to the SINGLETON
  :class:`EventLog`.
- ``events`` - list every entry recorded so far.
"""
