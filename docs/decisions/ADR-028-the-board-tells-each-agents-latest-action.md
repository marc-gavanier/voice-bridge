# ADR-028 — The board tells each agent's latest action

**Date**: 2026-11-15
**Status**: accepted, extends [ADR-016](ADR-016-the-bridge-keeps-and-speaks-the-board-of-agents.md) and [ADR-022](ADR-022-the-board-of-agents-heals-and-says-when-it-cannot-be-trusted.md)

## Context

The board of agents ([ADR-016](ADR-016-the-bridge-keeps-and-speaks-the-board-of-agents.md)) tells which agents work, since when and on what task, but not what each one is doing now. Asked how a task goes, Claude can only say that it runs, when the person wants to hear « it has been waiting for the CI for two minutes ».

The [hooks reference](https://code.claude.com/docs/en/hooks.md), read on 2026-11-15, lists `agent_id` and `agent_type` among the common input fields: `agent_id` identifies the subagent the hook fires in, and `agent_type`, its type, is present when the hook fires inside a subagent. `PreToolUse` adds `tool_name`, `tool_input` and `tool_use_id`, with no time of the call. The reference documents the fields of `tool_input` per tool: `command` and an optional `description` for `Bash`, an absolute `file_path` for `Read`, `Edit` and `Write`, `url` for `WebFetch`, `query` for `WebSearch`, `pattern` for `Grep` and `Glob`, `description` and `prompt` for `Agent`. A command hook with `"async": true` runs in the background, receives the same input, and cannot block or change the call. [ADR-015](ADR-015-the-main-agent-delegates-in-voice-sessions.md) found in #3 that `agent_id` is absent from the main agent's calls and present on any subagent's, in the foreground or the background.

## Decision

- **The activity hook also runs on `PreToolUse`, in the background.** It sits beside the tool hook in the same `"*"` matcher. The tool hook stays waited for, since it must answer before the tool runs; the activity hook is async, so an agent never waits on the bridge.
- **A call carrying an `agent_id` becomes an action.** The hook sends the bridge the agent's id, a short action and the moment the hook runs. A call without `agent_id`, the main agent's, sends nothing.
- **The action says what the agent does, never what it handles.** A `Bash` call is told by its own `description`, or by `Bash` alone without one, never by its command. `Read`, `Edit` and `Write` give the file's name, never its path or content; `WebFetch` the page's host, never its address; `Agent` and `Task` the task's description; `WebSearch` the query; `Grep` and `Glob` the pattern. Any other tool is told by its name. The action is folded on one line and cut at 120 characters.
- **The board keeps the latest action of each agent at work.** Each agent has `last_action`, `last_action_at` and `actions`, the count of actions heard. An action older than the latest known is counted but replaces nothing, so `last_action_at` never goes back in time. An action of an agent that is not at work changes nothing; a finished agent keeps its latest action. The `board` tool returns the three fields for every agent, at work or finished.
- **The `board` tool's description says so**, in the nine language packs, so that Claude uses the latest action to tell what a task is doing.

## Consequences

- Claude can answer « what is it doing? » with the latest action and how long ago it happened, from the board's `now`.
- Every tool call of the session, the main agent's included, starts one more `uv run` process, in the background; the main agent's ends without contacting the bridge.
- The moment is taken when the hook starts, after `uv run`'s startup, not when the tool was called; its startup varies by a few hundred milliseconds ([ADR-022](ADR-022-the-board-of-agents-heals-and-says-when-it-cannot-be-trusted.md)). Two calls made within that span, such as parallel calls of one message, may be ordered either way; calls seconds apart, the usual case, are ordered right.
- The action is the call about to run: a command that runs for minutes, such as watching the CI, stays the latest action, with its moment, until the agent's next call, which is what the person wants to hear.
- A command without a `description`, optional in the reference, is told only as `Bash`.
- The bridge logs each action as `agent … did '…'`, one line per tool call of an agent.
- A session started before this change keeps the hooks it was launched with: the settings come from `voice-bridge-claude-settings`, run by `claude-voice.sh` at launch, so the launcher must be run again for the actions to reach the board.

## Alternatives considered

- **`PostToolUse` instead of `PreToolUse`**: it fires only once the tool has finished, so a long command, the case that matters, would show the previous action for its whole run.
- **Wait for the hook on `PreToolUse`**: it would keep the order of the actions, but would delay every tool call of every agent by the hook's startup.
- **Stamp the action when the bridge hears it**: the hooks run in the background, and an older action heard later would then replace a later one.
- **Send the command, the path or the address**: more precise, but a command can carry secrets and a path or a query string personal data, which the bridge would keep and log, and Claude would read back aloud.
- **Read each agent's transcript to find its latest action**: the transcripts are Claude Code's internal format, and reading them on every board read would cost more than one message per call.
