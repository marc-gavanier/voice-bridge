# ADR-008 — Dev tools from uv and official hooks, pinned with their version

**Date**: 2026-11-10
**Status**: accepted

## Context

The checks run through prek, locally and in CI. Until now every tool was a Python package in the dev dependencies, run by a local hook through `uv run --frozen`: uv's `exclude-newer` refuses versions younger than ten days, `uv audit` checks them, and Renovate updates them with the same delay.

Issue #19 adds tools that are not written in Python. zizmor publishes its own wheels on PyPI. actionlint does not: its author publishes Go binaries, a Docker image and an official prek and pre-commit hook. The only package on PyPI, actionlint-py, is a third-party wrapper.

A remote hook is pinned by its `rev`, and the workflows pin their actions by `uses:`. A tag can be moved after the fact; a full commit SHA cannot. But the repository bans comments in code and configuration, and both Renovate managers learn the version of a SHA pin from a comment next to it. The [pre-commit manager](https://docs.renovatebot.com/modules/manager/pre-commit/) reads `rev: <sha>  # frozen: vX.Y.Z`, as written by `pre-commit autoupdate --freeze`. The [github-actions manager](https://docs.renovatebot.com/modules/manager/github-actions/) reads `uses: owner/repo@<sha> # vX.Y.Z`, and skips a bare SHA because it cannot tell which tag the commit belongs to. The action pins carried no version, so Renovate had never updated them.

## Decision

- A tool published on PyPI by its author is a dev dependency, run by a local hook through `uv run --frozen`, and in CI by the same command.
- A tool whose author publishes no Python package comes from the author's official prek hook as a remote repository. actionlint is the only one: `rhysd/actionlint`, hook `actionlint`. The CI runs it through `uv run --frozen prek run --all-files actionlint`.
- Remote hooks and actions are pinned to a full commit SHA followed by their version, in the format Renovate reads: `# frozen: vX.Y.Z` after a `rev`, `# vX.Y.Z` after the SHA of a `uses:`. Renovate's pre-commit manager is enabled (`:enablePreCommit`) and keeps the ten-day `minimumReleaseAge`.
- Comments stay banned in code and configuration, with one exception: these version annotations, read by tools next to a pinned digest. Nothing else may follow them.

## Consequences

- One path for every Python tool: locked in `uv.lock`, delayed ten days, audited and updated by Renovate.
- actionlint is built from source by prek: on first use, prek downloads the latest Go toolchain that satisfies actionlint's `go.mod` from go.dev, then runs `go install`. No system Go is needed, locally or in CI, but the toolchain version is not pinned and no release-age delay applies to it, and the first run needs network access to go.dev, the Go module proxy and github.com.
- Renovate updates both the hook and the actions, SHA and version together. A pin without its annotation would be left behind for good, silently.
- actionlint runs ShellCheck on `run:` blocks only if `shellcheck` is on the `PATH`. Under `uv run prek` and in CI, the dev dependency `shellcheck-py` provides it. The git hook calls prek directly, so a commit made outside the virtual environment skips ShellCheck on the workflows without warning. A system ShellCheck, from the distribution's official package, is therefore recommended but optional: without it the commit hook still passes, and CI checks the `run:` blocks on every pull request. `AGENTS.md` and `CONTRIBUTING.md` say so. A third-party Go port of ShellCheck as an `additional_dependencies` of the hook was set aside, for the same reason as actionlint-py.
- The ban on comments now has an exception, kept narrow so that reasoning still goes in commit messages and ADRs.

## Alternatives considered

- **actionlint-py**, as a dev dependency like the other tools. It is a third-party wrapper that ships no wheel: installing it downloads the actionlint binary from GitHub and checks it against a SHA-256 it carries. It adds a trust in a maintainer who is not actionlint's author, and network access at install time.
- **A bare SHA**, with no annotation, which keeps the configuration free of comments. Renovate cannot tell its version: the github-actions manager skips it, and the pre-commit manager reads the SHA as a tag name that matches no release. The pins would never be updated.
- **A tag**, such as `rev: v1.7.12`, which Renovate updates natively and which shows the version without a comment. A tag can be moved to other code after review, which a SHA rules out.
