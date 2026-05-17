# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chris <goabonga@pm.me>

"""Core type aliases for the Tripack dependency injection contracts.

A :data:`DependencyToken` is anything by which a binding can be looked
up in the container: typically a class (the canonical case), but also
a plain string (named bindings) or any other hashable value
(composite tokens like ``("clock", "primary")``).
"""

from collections.abc import Hashable
from typing import Any

type DependencyToken = type[Any] | str | Hashable
