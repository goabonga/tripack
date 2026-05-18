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
│   ├── pyproject.toml              # path deps -> packages/
│   ├── uv.lock
│   ├── src/fastapi_basic/...
│   └── tests/
├── typer-basic/
└── click-basic/
```

## How the deps are wired

The examples depend on Tripack via **local path sources**
during pre-publication. The `pyproject.toml` of each example
declares Tripack as a normal dependency and overrides its
source to point at the in-repo packages:

```toml
[project]
dependencies = [
    "tripack-container",
    # ... framework-specific deps
]

[tool.uv.sources]
tripack-contracts = { path = "../../packages/tripack-contracts", editable = true }
tripack-runtime = { path = "../../packages/tripack-runtime", editable = true }
tripack-container = { path = "../../packages/tripack-container", editable = true }
```

`uv sync` inside the example resolves Tripack from the local
source tree; changes to `packages/` are picked up immediately
without a PyPI round-trip. The `editable = true` makes the
install track the source files live, which is what we want for
a dev-loop example.

### Why path sources and not PyPI?

The examples need to be testable and shippable **before** any
Tripack package is on PyPI. Using path sources unblocks the
integration tests on day one. The trade-off is small: the
example dependencies do not exercise the PyPI installation
path, but the wiring code, the framework adapters, and the
test approach are identical to what a real consumer would
write.

After the first PyPI release of the three packages, the
recommended migration is one line per example:

```diff
 [tool.uv.sources]
-tripack-contracts = { path = "../../packages/tripack-contracts", editable = true }
-tripack-runtime = { path = "../../packages/tripack-runtime", editable = true }
-tripack-container = { path = "../../packages/tripack-container", editable = true }
+# (remove this section; the project dependencies above now
+#  resolve against PyPI like any other package)
```

Or, equivalently, pin a minimum version in `[project]
dependencies` (`tripack-container>=0.1`) and drop the local
sources entirely. Each example's `uv.lock` will then resolve
the published wheels.

## Running an example

```bash
cd examples/fastapi-basic
uv sync                # resolves Tripack from ../../packages/...
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
