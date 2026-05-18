# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""End-to-end tests for the Typer + Tripack integration example."""

from __future__ import annotations

from typer.testing import CliRunner
from typer_basic.cli import app
from typer_basic.wiring import build_container


def test_now_command_prints_clock_reading() -> None:
    """``now`` resolves the SINGLETON Clock and prints its reading."""
    runner = CliRunner()
    with build_container() as container:
        result = runner.invoke(app, ["now"], obj=container)
    assert result.exit_code == 0
    assert "now =" in result.stdout


def test_record_command_appends_to_singleton_log() -> None:
    """``record`` accumulates entries in the SINGLETON EventLog across invocations."""
    runner = CliRunner()
    with build_container() as container:
        first = runner.invoke(app, ["record", "hello"], obj=container)
        second = runner.invoke(app, ["record", "world"], obj=container)
        listing = runner.invoke(app, ["events"], obj=container)
    assert first.exit_code == 0
    assert "recorded (1 entries total)" in first.stdout
    assert second.exit_code == 0
    assert "recorded (2 entries total)" in second.stdout
    assert listing.exit_code == 0
    assert "hello" in listing.stdout
    assert "world" in listing.stdout


def test_fresh_container_has_empty_log() -> None:
    """Each ``build_container`` produces an isolated EventLog."""
    runner = CliRunner()
    with build_container() as container_a:
        runner.invoke(app, ["record", "only-on-a"], obj=container_a)
    with build_container() as container_b:
        listing = runner.invoke(app, ["events"], obj=container_b)
    assert listing.exit_code == 0
    assert "only-on-a" not in listing.stdout
    assert listing.stdout.strip() == ""
