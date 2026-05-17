# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

from tripack_runtime import __version__


def test_version_is_a_non_empty_string() -> None:
    assert isinstance(__version__, str)
    assert __version__
