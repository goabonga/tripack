## Description

<!-- Describe what this PR does and why. -->

## Type

<!-- Check the one that applies: -->

- [ ] `feat` - New feature
- [ ] `fix` - Bug fix
- [ ] `docs` - Documentation
- [ ] `refactor` - Code refactoring
- [ ] `test` - Adding or updating tests
- [ ] `chore` - Maintenance
- [ ] `ci` - CI / release pipeline

## Scope

<!-- Which package(s) does this PR touch? -->

- [ ] `tripack-contracts`
- [ ] `tripack-runtime`
- [ ] `tripack-container`
- [ ] repo-level (workspace, CI, docs)

## Changes

<!-- List the main changes introduced by this PR: -->

-

<!-- === Per-type guidance (delete sections that don't apply) === -->

<!-- FEAT: New feature -->
<!-- - Describe the feature and its use case -->
<!-- - Mention any new dependencies added -->
<!-- - Include a usage example if applicable -->

<!-- FIX: Bug fix -->
<!-- - Describe the bug and how to reproduce it -->
<!-- - Explain the root cause -->
<!-- - Describe the fix and why it works -->

<!-- DOCS: Documentation -->
<!-- - What documentation was added/updated? -->
<!-- - Link to the relevant section if applicable -->

<!-- REFACTOR: Code refactoring -->
<!-- - What was refactored and why? -->
<!-- - Confirm there is no behavior change -->

<!-- TEST: Tests -->
<!-- - What is being tested? -->
<!-- - Describe edge cases covered -->

<!-- CHORE / CI: Maintenance / pipeline -->
<!-- - What maintenance task was performed? -->
<!-- - Any impact on the release pipeline or downstream consumers? -->

## Related Issues

<!-- Link related issues: Closes #123, Fixes #456 -->

## Checklist

- [ ] Commits follow [Conventional Commits](https://www.conventionalcommits.org/) and target the right package via the scope (`feat(runtime): ...`)
- [ ] Branch is up to date with `main`
- [ ] `uv sync --all-packages` succeeds
- [ ] `uv run pytest` passes for every touched package
- [ ] `uv tool run multicz validate --strict` passes
- [ ] SPDX license headers are present (`python scripts/add_license_header.py --path . --types py,yml,toml --check`)
- [ ] No `Co-Authored-By` trailer in commit messages
