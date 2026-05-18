# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Tripack + Typer integration example.

A small CLI that demonstrates wiring a Tripack container into
a `Typer` application. The pattern is short:

- the entrypoint builds the container under a ``with`` block;
- ``typer.run`` (or the explicit ``app(obj=container)`` form)
  passes the container along as the Click context object;
- each command takes a ``typer.Context`` parameter and pulls
  the services it needs via ``container.resolve``.

Commands:

- ``now``    - print the current SINGLETON :class:`Clock`
  reading.
- ``record`` - append a message to the SINGLETON
  :class:`EventLog`.
- ``events`` - list every entry recorded so far.
"""
