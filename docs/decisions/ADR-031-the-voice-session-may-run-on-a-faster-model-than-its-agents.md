# ADR-031 — The voice session may run on a faster model than its agents

**Date**: 2026-11-15
**Status**: accepted, as an experiment

## Context

In a voice session the main agent talks and delegates: [ADR-015](ADR-015-the-main-agent-delegates-in-voice-sessions.md) refuses it the working tools, so it answers, says what it will do and hands every task to a background agent. Its turns are short and its time is heard: the log analysis of 2026-11-14 measured 3.65 s in median for Claude, from the words pushed to its first reply, the largest step of `response.latency`. The work that needs the strongest model is done by the agents.

Claude Code documents what it takes to run the two on different models:

- The main session's model is set, from highest priority, by `/model`, the `--model` flag, `ANTHROPIC_MODEL`, then the `model` key of a settings file, which accepts an alias such as `sonnet` or `opus` or a full name such as `claude-sonnet-5-5` ([model configuration](https://code.claude.com/docs/en/model-config)).
- A subagent runs on the first of: the model Claude passes when it starts it, the `model` field of its definition, `CLAUDE_CODE_SUBAGENT_MODEL`, then the main session's model. The built-in general-purpose agent has no `model` field; Explore runs on Opus with a Claude subscription whatever is set; Plan and forks follow the session unless `CLAUDE_CODE_SUBAGENT_MODEL_FORCE` is `1`, and a fork follows it even then ([subagents](https://code.claude.com/docs/en/sub-agents#choose-a-model), [environment variables](https://code.claude.com/docs/en/env-vars)).
- Variables in the `env` block of a settings file apply to the session, `CLAUDE_CODE_SUBAGENT_MODEL` included.

The launcher already passes Claude Code a settings file written by `voice-bridge-claude-settings` from the config, so that hooks never read the config themselves.

## Decision

- Two optional settings, `claude.model` and `claude.subagent_model`, unset by default. `voice-bridge-claude-settings` writes the first as the `model` key and the second as `CLAUDE_CODE_SUBAGENT_MODEL` in the `env` block of the settings it already prints; unset, it writes neither, and the session runs as before.
- A value is a model name or alias: lower-case letters, digits, dots and dashes, starting with a letter or digit, with an optional `[1m]`. An empty value or one starting with a dash stops the start, so a value is never read as an option.
- The run's attributes name both, `voice_bridge.claude.model` and `voice_bridge.claude.subagent_model`, `default` when unset, so that the turns of each run can be compared.
- The experiment sets the session on Sonnet 5.5 and the agents on Opus 5.5. It compares the median of the `claude` span and of `response.latency` with the baseline of 3.65 s for Claude, and the speaker judges whether the answers he hears and the tasks the agents bring back keep their quality. The setting stays or goes on that result.

## Consequences

- With the settings unset nothing changes: the hooks' settings are the same and Claude Code keeps the model of its own settings.
- The models change at the next launch of `scripts/claude-voice.sh`, like the hooks' settings; `/model` still changes the session's model while it runs.
- The settings' `model` key ranks below `--model` and `ANTHROPIC_MODEL`: one given to the launcher or set in its shell wins over `claude.model`.
- A fork, and Plan, run on the session's model: a task the session forks rather than delegates runs on the faster model. A model Claude passes when it starts an agent wins over `claude.subagent_model`.
- Effort stays at each model's default, `medium` for Sonnet 5.5 and Opus 5.5, so that the experiment changes one thing.

## Alternatives considered

- **The `--model` flag and an exported `CLAUDE_CODE_SUBAGENT_MODEL` in `claude-voice.sh`**: it ranks higher, but the launcher would have to read the config, or a second output of `voice-bridge-claude-settings`; the settings file already carries what the config decides for Claude Code.
- **`CLAUDE_CODE_SUBAGENT_MODEL_FORCE`**: it would put Plan and agents with their own `model` on the agents' model too, and forbid Claude to choose one; the experiment needs only the general-purpose agents the session starts, so it is left out until a run shows otherwise.
- **A lower effort on the session instead of a smaller model**: `--effort` and `effortLevel` exist and may lower the latency too, but changing both at once would not tell which one helped.
