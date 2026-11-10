# ADR-006 — Generated diagrams, never committed

**Date**: 2026-11-10
**Status**: accepted

## Context

A diagram drawn by hand falls out of date as soon as the code moves on, and nothing tells. The repository's rule is also never to commit what a build produces.

Only what the code contains can be drawn from it. The dependencies between packages can; the path of a voice turn, from the phone to Claude and back, is behaviour at run time and cannot.

Two tools were tried on the code:

- **pyreverse**, from pylint, writes Mermaid, which GitHub renders in a README. It names modules by their last part, so the four `domain` and the four `abilities` packages merge into one node each: the diagram is wrong.
- **pydeps** draws the import graph with Graphviz. At the module level it is accurate but unreadable; at the level of features and libraries it is readable, and two runs give byte-identical files.

## Decision

Draw the architecture with pydeps, at the level of features and libraries, from the imports. Its settings live in `[tool.pydeps]` in `pyproject.toml`, so `uv run pydeps src/voice_bridge` is the whole command. Its output, `docs/architecture.svg`, is ignored by git, and the README gives the command instead of the picture. The path of a voice turn is described in words.

## Consequences

- The diagram can never disagree with the code.
- It is not visible on GitHub: it takes a clone, the development dependencies and Graphviz.
- The import-linter contracts remain the executable statement of the architecture; the diagram only shows it.

## Alternatives considered

- **Commit the SVG and check it in a hook and in CI**, failing when it differs from a fresh one. Always up to date and visible on GitHub, but a build output in the repository.
- **Generate it in CI and publish it**, on GitHub Pages or as an artifact, linked from the README. Visible without a clone, at the cost of a publication to maintain.
- **Mermaid written by hand.** Rendered by GitHub, but not generated, so it would drift from the code.
