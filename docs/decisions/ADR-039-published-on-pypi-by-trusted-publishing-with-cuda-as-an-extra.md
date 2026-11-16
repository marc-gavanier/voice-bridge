# ADR-039 — Published on PyPI by trusted publishing, with CUDA as an extra

**Date**: 2026-11-16
**Status**: accepted, publishing blocked

## Context

The bridge is installed from a clone with `uv sync`, and every dependency is mandatory: about a gigabyte of NVIDIA packages comes even on a machine that has CUDA already or that transcribes on the CPU (#17). The survey of #17 found that almost every popular Python project publishes to PyPI with trusted publishing, an OpenID Connect token that GitHub issues to one workflow and PyPI trusts, with no stored secret; uv's documentation gives a reference workflow that builds with `uv build`, smoke-tests the wheel and the sdist, then publishes from a job in a `pypi` environment.

On 2026-11-16, the version in `pyproject.toml` was `0.1.0`, written by hand; the repository had no tag and no GitHub release, and nothing had ever been published. commitizen was configured to check commit messages only.

On 2026-11-16, the name `voice-bridge` was free on PyPI: both its JSON API and its simple index answered 404. The wheel built by `uv_build` holds the package and its language files, and imports every entry point once installed alone, without the repository.

## Decision

- `nvidia-cublas-cu12` and `nvidia-cudnn-cu12` move to a `cuda` extra. `uv sync` and a plain install bring no NVIDIA package; `whisper.device` stays `auto`, so Whisper runs on the CPU without a GPU, or on the GPU with the CUDA libraries of the system. `scripts/with-cuda.sh` and the launcher add `--extra cuda`, so a clone runs on the GPU as before ([ADR-004](ADR-004-cuda-libraries-from-pip.md)).
- The `Release` workflow, `.github/workflows/release.yml`, has two jobs. `build`, with `contents: read` only, runs `uv build --no-sources`, then imports the channel's entry point from the wheel and from the sdist, each installed alone, and checks that no `nvidia` package came with them. `publish`, in the `pypi` environment and with `id-token: write` as its only permission, uploads them with the official `pypa/gh-action-pypi-publish`, pinned by digest, which also signs PEP 740 attestations. No PyPI token is stored anywhere.
- The bridge is published as an alpha, in 0.x versions, from its first release: under 0.x, a breaking change, such as the reorganisation of the settings file by port of [ADR-035](ADR-035-every-brick-of-the-voice-chain-is-swappable-behind-a-port.md), bumps the minor version, as [Semantic Versioning](https://semver.org/#spec-item-4) allows for 0.x. The classifier `Development Status :: 3 - Alpha` says so on PyPI. Version 1.0.0 is chosen by hand when the bridge leaves alpha.
- commitizen makes the versions: `cz bump` reads the Conventional Commits since the last tag, writes the version in `pyproject.toml` and `uv.lock` through its `uv` provider, updates `CHANGELOG.md` and creates the `vX.Y.Z` tag. `major_version_zero` keeps a breaking change from leaving 0.x by itself.
- The release workflow keeps no cache, so that nothing a pull request wrote can reach a published package.
- Until the blockers below are lifted, the workflow starts only by hand (`workflow_dispatch`): no tag can publish by accident. Once they are, its trigger becomes a push of a `v*` tag, the tag that `cz bump` creates.

## Blockers

Nothing is published until all of these are cleared:

- The pending trusted publisher on pypi.org, which only the owner of the PyPI account can add: owner `marc-gavanier`, repository `voice-bridge`, workflow `release.yml`, environment `pypi`, for the project `voice-bridge`. The `pypi` environment is created in the repository's settings at the same time.
- The commits of this change are not signed yet, and `main` refuses unsigned commits.
- The name `voice-bridge` must still be free when the publisher is added: a pending publisher does not reserve it.

## Consequences

- A machine with CUDA already, or without a GPU, saves about a gigabyte; `uv tool install 'voice-bridge[cuda]'` brings the libraries, but an install from PyPI has no `scripts/with-cuda.sh`, so `LD_LIBRARY_PATH` must point at them as faster-whisper documents, until a later decision ships the wrapper as a command.
- The CI's `uv sync --locked` no longer installs the NVIDIA packages, so its uv cache shrinks.
- A leaked token cannot publish: only a run of `release.yml` in the `pypi` environment of this repository can.
- `scripts/claude-voice.sh`, `scripts/voxtral.sh` and the GitHub release built from the changelog stay outside this change, as #17 lists.

## Alternatives considered

- **An API token stored as a secret**: works everywhere, but a long-lived secret to rotate and to leak, which PyPI itself advises against when trusted publishing is available.
- **`uv publish` instead of `pypa/gh-action-pypi-publish`**: the uv guide's choice and one tool fewer, but the PyPA action is the reference implementation of trusted publishing and creates the attestations without further steps.
- **Keeping the CUDA libraries mandatory**: a turnkey GPU setup for everyone, at a gigabyte for those who do not need it.
- **Waiting for the architecture work of ADR-035 before the first release**: the settings would break before anyone installs the package, but the bridge would stay unpublished for the whole of #77 to #85; 0.x versions allow those breaks.
- **PEP 440 pre-releases such as `1.0.0a1`**: the usual way to publish an alpha of a project already at 1.x, but the bridge never had a 1.x version, and pre-releases are skipped by installers unless asked for.
- **A tag trigger guarded by a condition** until the blockers are lifted: the trigger would already be in place, but one wrong condition would publish; starting by hand only is plainer.
