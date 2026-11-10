# Contributing

Thank you for wanting to improve voice-bridge. This file tells you how to propose a change; the rest lives elsewhere and is not repeated here:

- the [README](README.md) explains what the bridge does, how to run it and how the code is laid out;
- [`AGENTS.md`](AGENTS.md) lists the rules the code and the tests follow, for people as much as for coding agents;
- the [ADRs](docs/decisions) explain why the project is built the way it is.

To report a vulnerability, do not open an issue: follow the [security policy](SECURITY.md).

## Issues

Bugs, questions and ideas are welcome as [issues](https://github.com/marc-gavanier/voice-bridge/issues). For a bug, the README's [Diagnose](README.md#diagnose) section says which log lines help; the log holds what was said to the bridge, so remove anything private before pasting it.

Before a large change, open an issue to talk about it first.

## Set up

You need Linux, [uv](https://docs.astral.sh/uv/), the system `libopus0` for the tests and a system `gitleaks` for the commit hook. A system `shellcheck` is recommended (`sudo apt install shellcheck` on Debian and Ubuntu), so that the commit hook also checks the workflows' `run:` blocks; without it, only CI does. Running the bridge for real also needs an NVIDIA GPU, a Mumble server and Claude Code, as the README's [Requirements](README.md#requirements) say; the checks do not.

```bash
uv sync
uv run prek install
```

The second command installs the hooks that check each commit, each commit message and each push.

## Run the checks

```bash
uv run prek run --all-files
```

This runs over every file the checks the CI runs on a pull request; the hooks check commit messages when you commit and the dependencies when you push. [`AGENTS.md`](AGENTS.md#checks) says what each check holds. The Ruff hooks fix what they can, so review the diff afterwards. When you change a domain, `uv run mutmut run` also tells you whether the tests catch faults injected into it.

## Propose a change

- Work on a branch named after the change's [Conventional Commits](https://www.conventionalcommits.org) type, such as `fix/log-dismissed-sounds`, and keep one change per pull request.
- Write each commit message as a Conventional Commit: a lower-case subject without a final period, and a body that says why.
- Sign your commits ([how](https://docs.github.com/en/authentication/managing-commit-signature-verification/signing-commits)). `main` only accepts signed commits, and the merge keeps your commits as they are, so they must carry your own signature.
- Cover the change with tests: branch coverage stays at 100 %. Keep the README in step with what the code does.
- When the change picks a library, a protocol or a rule, or sets aside a plausible alternative, record it in an ADR in [`docs/decisions`](docs/decisions).
- Never bypass the hooks with `--no-verify`.

Then open a pull request against `main`. Both CI jobs, `checks` and `secrets`, must be green.

## Tools, AI included

Use whatever tools you like, AI included: an AI is a tool like any other, on the same footing as an IDE, a keyboard and a mouse. You are responsible for what you submit and must understand it; the same checks and the same review apply, whatever helped write it.

## How a pull request is merged

Pull requests are not merged with GitHub's button: its rebase merge would recreate the commits without their signatures. Once the pull request is ready, the maintainer fast-forwards `main` to its branch from a local clone, as the README's [Merging](README.md#merging) section shows. If `main` has moved on in the meantime, you may be asked to rebase your branch onto it, which keeps the history linear.
