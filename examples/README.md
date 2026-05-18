# Tripack integration examples

This directory holds **end-to-end integration examples** that
show how to wire Tripack into popular Python frameworks.
Three examples ship today: a web service with **FastAPI**, a
CLI with **Typer**, and a CLI with **Click**.

Each example is a **standalone project** with its own
`pyproject.toml`, `uv.lock`, `src/`, and `tests/`. They are
deliberately kept **outside** of the workspace
(`[tool.uv.workspace] members` in the root `pyproject.toml`
lists only `packages/*`), so the examples install Tripack the
same way a real consumer would.

```
examples/
├── README.md                       # this file
├── fastapi-basic/
│   ├── pyproject.toml              # tripack-container from PyPI
│   ├── uv.lock
│   ├── src/fastapi_basic/...
│   └── tests/
├── typer-basic/
└── click-basic/
```

## How the deps are wired

Each example declares `tripack-container` (and the framework
of its choice) as a normal PyPI dependency:

```toml
[project]
dependencies = [
    "tripack-container>=0.2.0",
    # ... framework-specific deps
]
```

`uv sync` inside the example resolves the published wheels
from PyPI. `tripack-runtime` and `tripack-contracts` come in
transitively through `tripack-container`'s metadata, so the
example only has to pin the high-level entrypoint.

## Running an example

```bash
cd examples/fastapi-basic
uv sync                # resolves Tripack from PyPI
uv run pytest          # runs the example's test suite
uv run python -m fastapi_basic   # starts the demo service
```

Each example's `README.md` documents the runtime entrypoint
and any framework-specific setup.

## Testing the examples

The workspace CI runs the examples in a dedicated job (added
in 8.5). The job is gated on changes under `examples/`, so
core-only changes do not pay the cost of installing
FastAPI / Typer / Click for unrelated work. When an example
breaks because of a core API change, the example **fails
loudly** at install or test time - that is precisely the
signal we want, and it is the same signal a PyPI-pinned
example would produce.

The examples do **not** gate the package release: an
out-of-date example is a docs-side issue, not a reason to
block shipping `tripack-container`. The CI job is "informational"
in that sense - it surfaces the breakage immediately for a
follow-up PR rather than blocking the release.
