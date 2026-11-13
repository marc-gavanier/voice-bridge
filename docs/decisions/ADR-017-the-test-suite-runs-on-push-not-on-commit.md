# ADR-017 — The test suite runs on push, not on commit

**Date**: 2026-11-13
**Status**: accepted

## Context

Every prek hook ran at each commit and again at each push, pytest included. On 2026-11-13, `uv run prek run --all-files --verbose` timed the whole suite with branch coverage at 51 s, while every other hook took under 4 s: basedpyright 3.6 s, validate-pyproject 2.9 s, the import-linter contracts 0.3 s, gitleaks 0.3 s, the rest 0.1 s or less.

Work goes test first, one small commit per behaviour, so a minute of waiting at each commit makes commits fewer and larger, and history harder to read. The tests concerned by a change already ran while writing it. History stays linear and commits are never squashed, so each commit is meant to read well on its own.

## Decision

- The `pytest` hook runs at the `pre-push` stage only, with `always_run`: a push runs the whole suite, with 100 % branch coverage, whatever files it changes. Its former filter on Python and TOML files missed what the tests also read, such as the Gherkin `.feature` files and `tests/fixtures`.
- Every other hook still runs at commit and at push; `uv audit` stays at push only, and commitizen at the commit message.
- Between commits, developers and agents run only the tests concerned, with `uv run pytest <paths> --no-cov`.
- `uv run prek run --all-files --hook-stage pre-push` runs every check, the tests included; the CI runs every check, the tests included, on each pull request and on `main`, as before.

## Consequences

- A commit takes a few seconds; a push takes about a minute more.
- A commit may break a test that a later commit in the same push fixes, and the push still passes: a commit in the middle of history can fail its tests. The tests concerned, run between commits, make it rare.
- `uv run prek run --all-files` no longer runs the tests; AGENTS.md and the README give the command that does.
- `git push --no-verify` skips the suite, and the CI still catches a failure before `main`.

## Alternatives considered

- **Keep the suite at commit**: every commit is known green, but costs a minute, which pushes toward fewer, larger commits.
- **pytest-xdist to run the suite in parallel**: it would shorten the wait without removing it, and adds a dependency and the risk of tests that share state failing only in parallel.
- **Rely on CI only**: nothing would run locally before a push, so a failure would show only minutes later on GitHub, after the branch is public.
