# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""End-to-end tests for the Click + Tripack integration example."""

from __future__ import annotations

from click.testing import CliRunner
from click_basic.cli import cli
from click_basic.wiring import build_container


def test_now_command_prints_clock_reading() -> None:
    """``now`` resolves the SINGLETON Clock and prints its reading."""
    runner = CliRunner()
    with build_container() as container:
        result = runner.invoke(cli, ["now"], obj=container)
    assert result.exit_code == 0
    assert "now =" in result.output


def test_record_command_appends_to_singleton_log() -> None:
    """``record`` accumulates entries in the SINGLETON EventLog across invocations."""
    runner = CliRunner()
    with build_container() as container:
        first = runner.invoke(cli, ["record", "hello"], obj=container)
        second = runner.invoke(cli, ["record", "world"], obj=container)
        listing = runner.invoke(cli, ["events"], obj=container)
    assert first.exit_code == 0
    assert "recorded (1 entries total)" in first.output
    assert second.exit_code == 0
    assert "recorded (2 entries total)" in second.output
    assert listing.exit_code == 0
    assert "hello" in listing.output
    assert "world" in listing.output


def test_fresh_container_has_empty_log() -> None:
    """Each ``build_container`` produces an isolated EventLog."""
    runner = CliRunner()
    with build_container() as container_a:
        runner.invoke(cli, ["record", "only-on-a"], obj=container_a)
    with build_container() as container_b:
        listing = runner.invoke(cli, ["events"], obj=container_b)
    assert listing.exit_code == 0
    assert "only-on-a" not in listing.output
    assert listing.output.strip() == ""
