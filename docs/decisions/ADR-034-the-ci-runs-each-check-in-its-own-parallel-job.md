# ADR-034 — The CI runs each check in its own parallel job

**Date**: 2026-11-16
**Status**: accepted

## Context

The `checks` job ran every check one after the other: file hygiene, `pyproject.toml`, the workflows, Ruff, basedpyright, the architecture contracts, the tests, the spelling, ShellCheck, `uv audit` and the commit messages. On the six runs of `Checks` on 2026-11-15, the job took 84 to 116 s, 96 s on average, and set the length of the run, since `secrets` ends in about 10 s.

On the run of 2026-11-15 at 23:17, the setup took 32 s (`libopus0` 5 s, setup-uv and its cache 23 s, `uv sync` 2 s), the tests 31 s with 3 s for the cache of the models, basedpyright 5 s and every other check under 3 s. A failure was only reported once the checks before it had passed, and a red run named one failing step.

The `main` ruleset requires the status checks `checks` and `secrets` by name. GitHub counts a required check whose job was skipped as passed, so a job that only aggregates others must fail when any of them did not succeed.

## Decision

- Seven independent jobs run in parallel, each with its own checkout, setup-uv with its cache and `uv sync`: `files` (pre-commit-hooks, validate-pyproject, ShellCheck, typos and, on a pull request, commitizen), `workflows` (actionlint and zizmor), `lint` (Ruff), `types` (basedpyright), `architecture` (import-linter, alint, deptry), `tests` (pytest with coverage) and `audit` (`uv audit`, which reads only the lockfile and skips `uv sync`).
- The shared steps are written once, as YAML anchors in `checks.yml`, which GitHub Actions supports since September 2025.
- A last job keeps the name `checks`, runs `if: always()` after the seven, and fails unless each of them succeeded, with [`re-actors/alls-green`](https://github.com/re-actors/alls-green). The ruleset keeps requiring `checks` and `secrets`, unchanged.
- Mutation testing stays a weekly workflow of its own.

## Consequences

- A run lasts about as long as its longest job, the tests: about 32 s of setup, 3 s of cache and 31 s of tests, so about 70 to 80 s with the aggregating job, against 96 s on average. The first push measures it.
- Each failing check shows as its own red job, and the others still report.
- The runners spend more minutes in total, one setup per job; the repository is public, so they cost nothing.
- A new check goes into the job of its kind, or into a new job added to the `needs` of `checks`; a job missing from that list would not block a merge.

## Alternatives considered

- **A composite action in `.github/actions/setup`**: the usual way to share steps, but zizmor's `self-repository` audit asks for GitHub's `uses: $/…` syntax, which actionlint 1.7.12 rejects (rhysd/actionlint#711), so one of the two checks would have had to be turned off.
- **Listing the seven jobs in the ruleset**: no aggregating job, but every new or renamed job would need a change of the ruleset by hand.
- **A shell step comparing `needs.*.result`**: the same check without a third-party action, but the maintained action is the common practice and handles every result, cancelled and skipped included.
- **pytest-xdist in the `tests` job**: it would shorten the longest job, but ADR-017 set it aside for the risk of tests that share state failing only in parallel.
