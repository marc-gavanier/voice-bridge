# ADR-022 — The board of agents heals and says when it cannot be trusted

**Date**: 2026-11-14
**Status**: accepted, partly supersedes [ADR-014](ADR-014-claude-codes-hooks-tell-when-claude-works.md) for how the hooks are run and fail, and [ADR-016](ADR-016-the-bridge-keeps-and-speaks-the-board-of-agents.md) for the rules of the board

## Context

The board of agents ([ADR-016](ADR-016-the-bridge-keeps-and-speaks-the-board-of-agents.md)) is only useful if Claude can rely on it completely. On 2026-11-14 it was wrong three ways ([#55](https://github.com/marc-gavanier/voice-bridge/issues/55)):

- Every hook started by loading `config.toml`, whose settings forbid unknown keys. A key added for a newer bridge, `speech.speed`, made every hook die before reading its input, from 20:32:27 on. Nothing reached the bridge, whose log stayed silent, and the board kept answering with its last state: two agents finished were still at work, and one started was missing. The tool hook died the same way, so the refusal of tools after a stop and the delegation rule of [ADR-015](ADR-015-the-main-agent-delegates-in-voice-sessions.md) were off without a sign.
- On a resume with `SendMessage`, Claude Code sends `SubagentStop` then `SubagentStart` with the same `agent_id`, 65 ms apart. The board added a second agent, lost the first start time, and listed the agent twice among the finished.

The [hooks reference](https://code.claude.com/docs/en/hooks.md), read on 2026-11-14, says that `SubagentStart` runs when Claude resumes a subagent too, and that `Stop` and `SubagentStop` carry `background_tasks`, present when Claude Code's task registry is reachable and empty when nothing is in flight. Each entry describes one task in flight, with its `id`, a `type` such as `shell`, `subagent`, `monitor` or `workflow`, a `status`, a `description`, and an `agent_type` for a subagent. [ADR-016](ADR-016-the-bridge-keeps-and-speaks-the-board-of-agents.md) found that a background agent's entry has the agent's id, and that the agent is still listed on its own `SubagentStop`.

The bridge's log shows that every message forwarded to Claude brought a `busy` from the `UserPromptSubmit` hook within a second, even while Claude worked, and within three seconds at worst.

## Decision

- **The hooks do not read the config file.** The activity hook takes the socket's path, the tool hook the stop flag's path and the language, both the bridge's log file, as options on their command line, with the bridge's defaults when one is missing. `voice-bridge-claude-settings`, run by `claude-voice.sh` at launch, reads the config once and prints the Claude Code settings that register the hooks with these values; it replaces the jq that wrote them.
- **A hook that fails is seen.** A hook that cannot reach the bridge, or fails, writes it to the bridge's log file, with the bridge's line format.
- **The board knows when it may be stale.** It notes the first message forwarded since the last `busy`. When 30 s pass without one, the `board` tool answers `"reliable": false`, with `unreliable_since` and a reason for Claude. A `busy` that comes later keeps the board unreliable, since news may have been lost meanwhile, and the bridge logs the silence. The next `Stop` or `SubagentStop` that lists the tasks reconciles the board and makes it reliable again.
- **A resume reopens the same entry.** A `SubagentStart` for an agent found among the finished moves it back to work, with its first start time, `resumed` counted and `resumed_at`; its next stop gives a single finished entry. A start for an agent already at work changes nothing. An agent appears at most once on the board.
- **The board heals from Claude Code's own list.** On a `Stop` or `SubagentStop` that carries `background_tasks`, only the entries of type `subagent` count. An agent once listed there and listed no more is finished, with an empty last message. A listed agent the board does not know, neither at work nor finished, is added at work with its description, from now. The agent whose own `SubagentStop` carries the list is left to that stop. A finished agent listed again is not reopened: only `SubagentStart` reopens an entry. A message without the list reconciles nothing.
- **`SubagentStart` and `SubagentStop` are waited for.** Their hooks are no longer async, so that Claude Code runs the stop's hook to its end before the start's, and the bridge hears them in that order. `UserPromptSubmit`, `Stop`, `StopFailure` and `SessionEnd` stay async.

## Consequences

- An edit of `config.toml`, valid or not, no longer silences the hooks of a running session. A config the bridge would refuse stops the launcher instead, before Claude Code starts. A change of the config that the hooks use, such as `language` or `activity_socket`, reaches them at the next launch, as it reaches the bridge.
- A hook that fails before Python starts, such as one whose entry point was renamed in the checkout it runs from, writes nothing to the log; the board then reports itself unreliable 30 s after the next forwarded message, and Claude Code keeps the error in the session's transcript.
- A message forwarded while Claude thinks for more than 30 s without calling a tool may make the board unreliable for a while, though nothing was lost; it is reliable again at the next stop that lists the tasks.
- A board made reliable again by a reconciliation is exact for the background agents at work, but the agents that finished during the silence have no last message, and a foreground agent whose stop was lost stays at work: a foreground agent never appears in `background_tasks`.
- An agent added by reconciliation is counted from the moment it was seen, not from its real start, which no hook told.
- A resume is a change of the count like any other: going from three agents to two then three again in 65 ms may be said twice when nobody speaks.
- Each agent's start and stop wait for one run of the hook, a few hundred milliseconds, before the agent goes on.
- `background_tasks` entries of another type, such as shells and workflows, are not shown on the board.

## Alternatives considered

- **Load the config leniently in the hooks, ignoring unknown keys**: smaller, but an invalid value would still silence them, and the hooks would still depend on a file that changes under a running session.
- **Set the values in the environment of Claude Code**: hooks inherit it, but so do every tool and agent Claude starts, and the values would be split between the command line of Claude Code and the settings file.
- **Mark the board unreliable from the hook itself**: a hook that cannot reach the bridge cannot tell it either.
- **Expect any news, not only `busy`, after a forwarded message**: an agent starting or finishing does not prove that the message reached Claude.
- **Reopen a finished agent that the list shows as running**: it would bring back an agent whose stop was heard just before a list read a moment earlier, as a ghost until the next stop.
- **Finish every agent at work missing from the list, foreground ones too**: an agent started by a background agent may never be listed, and would be finished while it runs.
- **Order the messages by a time the hook sends**: the hooks start through `uv run`, whose startup varies by more than the 65 ms between a stop and a resume, so the time taken in the hook would not order them either.
