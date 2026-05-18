# Stability and deprecation policy

This page is the contract between Tripack and its users about what is
part of the **public API**, how it is versioned, and how long it takes
between announcing a deprecation and removing the deprecated symbol.

## Public API surface

A symbol is part of the public API if and only if **all** of the
following are true:

- it lives in one of the three published packages
  (`tripack-contracts`, `tripack-runtime`, `tripack-container`); and
- it is re-exported via `__all__` from that package's top-level
  `__init__.py`; and
- its name does not start with an underscore.

Anything else - including imports that are technically reachable but
not listed in `__all__`, modules under `_private/`, and the entire
internals of `tripack-runtime` accessed bypassing
`tripack-container` - is **internal** and may change at any time
without prior notice.

The public API is rendered at
<https://goabonga.github.io/tripack/> and mirrored in the docstrings
shipped with each wheel.

## Deprecation lifecycle (n + 2 minors)

Tripack follows [Semantic Versioning](https://semver.org/) per
package - see
[`CONTRIBUTING.md`](https://github.com/goabonga/tripack/blob/main/CONTRIBUTING.md#commit-messages)
for the full commit-type to bump-level mapping. Removals of public
symbols are governed by the cycle below.

**The cycle is counted in *minor* versions, not majors.** Letting `M`
be the current major and `m` the current minor of a package:

| Version | What changes |
| --- | --- |
| **`M.m.*`** | The feature exists. No warning. |
| **`M.(m+1).0`** (next minor) | The feature is **deprecated**. The announcement is a `deprecate(<package>): ...` commit - a custom Conventional Commits type registered in `multicz.toml` that bumps the minor and routes the entry into `### Deprecated` of `CHANGELOG.md`. The code raises a `DeprecationWarning` on use, the migration path is documented on the site, and the feature still works. |
| **`M.(m+2).0`** (second minor after deprecation) | The feature is **removed**. The commit type is `remove(<package>): ...` - another custom multicz type that bumps the minor and routes to `### Removed` in `CHANGELOG.md`. Under the n+2 contract, a removal that respected the warning window is not a breaking change (consumers had two minor releases to migrate), so the major number `M` does not change. The `Removed` entry back-links to the original `Deprecated` entry. |

Concretely:

- "n + 2" means **two minor releases between announcement and
  removal**. Patches (`M.m.z`) never deprecate or remove. Majors
  (`(M+1).0.0`) are reserved for the bypass case below.
- The announcement and warning land in the release that introduces
  them - never in an earlier release.
- Code that triggers the deprecation continues to work until the
  second minor after the announcement. Don't skip the warning phase.
- The announcement commit uses the **`deprecate:`** type (not
  `feat:`). The removal commit uses **`remove:`** (not `feat:` and
  not `feat!:`). Both are custom types declared in `multicz.toml`
  under `[project.bump_rules]`, both bump the minor, and both route
  to a dedicated `CHANGELOG.md` section (`### Deprecated` and
  `### Removed` respectively). See the full mapping in
  [`CONTRIBUTING.md`](https://github.com/goabonga/tripack/blob/main/CONTRIBUTING.md#commit-messages).
- `feat!:` / `BREAKING CHANGE:` (and therefore a major bump) is
  reserved for changes that **bypass** the n+2 minor window -
  security fixes, fundamental design errors that cannot wait two
  minor cycles.

### Exceptions

- **Security fixes** may remove a vulnerable symbol without the
  deprecation window. The release notes explain why and link to the
  advisory.
- **0.x releases** (the current state of all three packages) follow a
  relaxed cycle: a deprecation introduced in v0.(y+1) may be removed
  in the same v0.(y+1) line, since semver explicitly allows breaking
  changes during the 0.x phase. The n+2 promise becomes binding at
  **v1.0**.

## How to deprecate (for maintainers)

Emit a `DeprecationWarning` from the deprecated entry point with
`stacklevel=2` so the warning points to the caller, not to the Tripack
internals:

```python
import warnings


def old_resolver():
    warnings.warn(
        "tripack.old_resolver is deprecated; use "
        "tripack_container.Container.resolve instead. "
        "Will be removed in tripack-runtime v1.3.0.",
        DeprecationWarning,
        stacklevel=2,
    )
    ...
```

The warning message MUST name:

1. the deprecated symbol;
2. the replacement (or "no replacement, drop the call");
3. the target removal version.

Checklist for a deprecation commit:

- [ ] `DeprecationWarning` raised with `stacklevel=2`
- [ ] Warning text names replacement + target removal version
- [ ] `packages/tripack-<name>/CHANGELOG.md` entry under `Deprecated`
- [ ] Zensical page updated with the migration path
- [ ] Conventional Commit type for the **announcement** is
      `deprecate(<package>): ...` (custom type, minor bump, routed
      to `### Deprecated`).
- [ ] Conventional Commit type for the **removal**, two minors
      later, is `remove(<package>): ...` (custom type, minor bump,
      routed to `### Removed`). Reserve `feat!:` / `BREAKING CHANGE:`
      only when the removal bypasses the n+2 window.

## How to ride deprecations safely (for consumers)

Pin to the **minor** of each Tripack package, not only the major:

```toml
dependencies = [
    "tripack-container ~= 1.3",   # accepts 1.3.x, rejects 1.4.x
]
```

Promote `DeprecationWarning` to errors at least once per minor bump in
your test suite so upcoming removals fail loud before they actually
land:

```bash
python -W error::DeprecationWarning -m pytest
```

Read the per-package `CHANGELOG.md` before every bump - every removal
is listed under a `Removed` section and back-references the original
`Deprecated` entry.
