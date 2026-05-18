# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Entrypoint: ``python -m click_basic [COMMAND] [ARGS...]``."""

from click_basic.cli import cli
from click_basic.wiring import build_container


def main() -> None:
    """Build the container, run the Click CLI, tear down on exit."""
    with build_container() as container:
        cli(obj=container)


if __name__ == "__main__":
    main()
