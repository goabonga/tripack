# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Entrypoint: ``python -m typer_basic [COMMAND] [ARGS...]``.

Builds the container, hands it to Typer via ``obj=``, and
relies on the ``with`` block to run the container's
``close`` once Typer returns (including the ``SystemExit``
that ``typer.run`` raises for a non-zero command result -
``__exit__`` still fires).
"""

from typer_basic.cli import app
from typer_basic.wiring import build_container


def main() -> None:
    """Build the container, run the Typer CLI, tear down on exit."""
    with build_container() as container:
        app(obj=container)


if __name__ == "__main__":
    main()
