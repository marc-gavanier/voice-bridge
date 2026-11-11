# AGENTS.md

voice-bridge lets a person talk to a Claude Code session over Mumble. The [README](README.md) explains what it does, how to configure and run it, and how the code is laid out; the [ADRs](docs/decisions) explain why. This file only lists what you need to change the code without breaking its rules.

## Setup

- `uv sync`, then `uv run prek install` to install the hooks for commit, commit message and push.
- uv brings Python 3.14. The tests also need the system `libopus0`, and the commit hook calls a system `gitleaks`. A system `shellcheck` is recommended (`sudo apt install shellcheck` on Debian and Ubuntu): without it, only CI checks the workflows' `run:` blocks.
- Every tool comes from the dev dependencies and runs through `uv run`, except actionlint, whose author publishes no Python package: prek builds it from its official hook, with a Go toolchain it downloads on first use ([ADR-008](docs/decisions/ADR-008-dev-tools-from-uv-and-official-hooks-pinned-with-their-version.md)).
- uv refuses package versions younger than ten days (`exclude-newer` in `pyproject.toml`), and Renovate waits as long. Do not lift the delay without a reason given in the commit, as was done for pytest-bdd.
- `pymumble-rev` is pinned to an exact version on purpose ([ADR-001](docs/decisions/ADR-001-pymumble-rev-as-the-mumble-client.md)).
- Anything that runs Whisper on the GPU goes through `scripts/with-cuda.sh` ([ADR-004](docs/decisions/ADR-004-cuda-libraries-from-pip.md)). The tests do not need it.

## Checks

Run them all before proposing a change; the CI runs the same ones on every pull request and on `main`:

```bash
uv run prek run --all-files
```

The Ruff, final newline and trailing whitespace hooks fix what they can, so this command may change files in the working tree: review the diff before committing.

What each gate holds:

- **Ruff** with every rule selected except docstrings, copyright and `COM812`; relative imports are banned. Fix the code rather than adding `noqa`: the source has none.
- **basedpyright** in `all` mode over `src` and `tests`. Stubs for untyped packages live in `typings/`. The source has no `type: ignore`.
- **import-linter**, four contracts in `pyproject.toml` ([ADR-005](docs/decisions/ADR-005-features-and-abilities-on-a-hexagonal-core.md)): entry points sit above configuration and features, which sit above libraries; features never import each other; inside a feature, `abilities` sit above `implementations`, above `domain`; a `domain` imports nothing but the standard library. Two features cooperate only through the wiring in `entrypoints/`.
- **alint** allows only the folders of the architecture: `features/<feature>/{abilities,domain,implementations}`, `libraries/<library>`, `configuration`, `entrypoints`. Tests mirror these folders, plus `tests/fixtures`. A new folder elsewhere fails.
- **pytest** with warnings as errors and **100 % branch coverage**. Only the entry points and `libraries/mumble/connection.py` are omitted, because they only wire tested parts; do not add to that list to make a change pass.
- **pytest-timeout** fails any test that runs longer than 60 seconds, so a deadlock fails instead of hanging; the slowest test takes about one second. Each CI job also has a `timeout-minutes`.
- **deptry** checks that declared and imported dependencies match.
- **pre-commit-hooks** check every text file: no merge conflict markers, no file over 500 KB, one final newline, no trailing whitespace, and TOML and YAML that parse. `.editorconfig` sets the same rules, and the indentation, for editors.
- **validate-pyproject** checks `pyproject.toml` against PEP 621 and the schemas of the tools it knows (Ruff, uv, among others); the sections of the other tools stay unchecked.
- **actionlint** checks the syntax and expressions of the workflows, and their `run:` blocks with ShellCheck; the commit hook finds it only on the `PATH`, so it skips that part silently without the recommended system `shellcheck`; **zizmor** checks their security (template injection, dangerous triggers, persisted credentials, unpinned actions), offline in the hook and online in CI, where the job's read-only token also lets it check for impostor commits and known vulnerable actions.
- **typos** checks the spelling of the code and the English text. The repository is written in English; a file wholly in another language carries the language code in its name (`fr.toml`, `de.md`, `*_es.py`…) and typos checks its name but not its content, through the `localized` file type in `[tool.typos.type.localized]` of `pyproject.toml`, which lists the globs of every language, as typos recommends for localized content. Tests of logic that does not depend on the language are written in English. Fix a flagged word rather than allowing it, unless it is a real word typos does not know.
- **commitizen** checks each commit message, and **uv audit** checks the dependencies before each push.

## Writing code

- Domains are pure functions on immutable values: a decision returns new state and commands, and the loops around it carry them out. Turn taking is `step(state, event) -> (state, commands)`.
- An ability states what it needs as a `typing.Protocol`; entry points build the implementations and pass them in, with no container.
- Concurrency is anyio task groups and memory streams, never threads.
- No comments or docstrings in the code or the configuration. The reasoning goes in the commit message or an ADR. The one exception is a version annotation that a tool reads next to a pinned digest: `# frozen: vX.Y.Z` after a prek `rev`, and `# vX.Y.Z` after the SHA of a `uses:` in the workflows ([ADR-008](docs/decisions/ADR-008-dev-tools-from-uv-and-official-hooks-pinned-with-their-version.md)).

## Writing tests

- Tests pass fakes written as small classes or functions, never mocks. `monkeypatch` is only used to set environment variables.
- Keep logic out of test bodies: no loop, branch or counting in a test. Build inputs in named helpers.
- Test names are sentences that state the behaviour, such as `test_an_asked_sentence_is_played`.
- The rules of turn taking are Gherkin scenarios in `tests/features/conversation/domain/turn_taking.feature`, run with pytest-bdd, one `Then` each. Change a rule there first.
- Domains also have Hypothesis property tests (`test_*_properties.py`) and are mutation-tested with `uv run mutmut run`, weekly in CI. Three equivalent mutants survive by design; a new survivor means a missing test.

## Trying a change for real

- `scripts/with-cuda.sh uv run voice-bridge-rehearsal` repeats everything said on the server, through hearing, transcription, synthesis and interruptions, without a Claude Code session.
- `uv run voice-bridge-recorder` records the bridge's voice as the server sends it, to tell a loss on the bridge's side from a loss between the server and the phone.
- The bridge logs to `~/.local/state/voice-bridge/log/voice-bridge.log`: what was heard, forwarded and spoken. The README's [Diagnose](README.md#diagnose) section maps symptoms to log lines.

## Commits and pull requests

- [Conventional Commits](https://www.conventionalcommits.org): `feat`, `fix`, `refactor`, `test`, `docs`, `build`. The subject is a lower-case sentence saying what the change does, without a final period; the body says why.
- One change per pull request, on a branch named after its type, such as `fix/log-dismissed-sounds`.
- `main` requires signed commits, a linear history and both CI jobs, `checks` and `secrets`, green. Pull requests are merged by fast-forward from a local clone, not with GitHub's button; the README's [Merging](README.md#merging) section gives the commands. Never push to `main` or force-push without being asked.

## Decisions and documentation

- Record a decision in `docs/decisions/ADR-NNN-title-in-words.md` when it picks a library, a protocol, a security rule or a project rule, or sets aside a plausible alternative. Follow the existing ADRs: Date, Status, then Context, Decision, Consequences, Alternatives considered. When a decision replaces an earlier one, update the earlier one's status.
- The Mermaid diagrams in the README are written by hand ([ADR-007](docs/decisions/ADR-007-hand-written-mermaid-for-the-system.md)): a change to a protocol, a process or turn taking updates them in the same pull request.
- The dependency diagram is generated with `uv run pydeps src/voice_bridge` and never committed ([ADR-006](docs/decisions/ADR-006-generated-diagrams-never-committed.md)). Nothing that a build produces is committed.
- Keep the README in step with what the code does: configuration keys, commands, diagnostics.
