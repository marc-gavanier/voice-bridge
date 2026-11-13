# ADR-014 — Claude Code's hooks tell when Claude works

**Date**: 2026-11-13
**Status**: accepted

## Context

The hold music played only after a reply whose `working` flag Claude set. It depended on Claude applying an instruction: on 2026-11-11 it stopped twice while a background agent still worked, because a reply came without the flag, and on 2026-11-13 it stayed silent for 19 s while Claude thought before its first reply, since nothing had announced work yet. Marc does not want the bridge to rely on Claude following such rules.

The [hooks reference](https://code.claude.com/docs/en/hooks.md), read on 2026-11-13, gives what is needed:

- `UserPromptSubmit` runs on typed prompts and also on the turns Claude Code starts on its own: a session-scoped scheduled task firing, a background subagent reporting back, a message from another session.
- `Stop` runs when the main agent has finished responding. Its `background_tasks` lists the tasks still in flight, shells, subagents, monitors, workflows, and is empty when nothing is; `session_crons` lists scheduled wakeups. It does not run after a user interrupt.
- `StopFailure` runs instead of `Stop` when an API error ends the turn; `SessionEnd` when the session ends.

## Decision

- Turn taking counts Claude as working from the moment the speaker's words are forwarded, and on a `ClaudeBusy` event, until a `ClaudeIdle` event. Claude's replies no longer change it. The music waits `hold_music.delay` after any voice still playing, and a sentence that starts playing cancels the music to come.
- `voice-bridge-activity-hook`, registered by `claude-voice.sh` as an async command hook on `UserPromptSubmit`, `Stop`, `StopFailure` and `SessionEnd`, sends `busy` on `UserPromptSubmit` and on a `Stop` with background tasks, and `idle` otherwise. Scheduled wakeups do not count as work, or a `/loop` would play music for its whole interval.
- The hook tells the bridge over a Unix socket at `activity_socket`, in the user's runtime directory: the standard local channel between two processes, readable by the user only, and instant, where a file would need polling. A hook that finds no bridge does nothing and prints nothing.
- The `working` flag leaves the `reply` tool, its description and the sentences about it in the instructions of the nine languages. A flag sent by a session still on former instructions is ignored.
- The music rises over `hold_music.fade_in` and falls over `hold_music.fade_out`.

## Consequences

- The music no longer depends on what Claude writes, and plays while Claude thinks before its first reply, while it works after a reply, and while background agents run.
- After an interrupt with Escape, no `Stop` runs: the music goes on until the speaker talks or the next turn ends.
- A prompt typed in the terminal also brings the music.
- The bridge's audio is one queue, so the fall of the music plays before the reply's voice and delays it by `hold_music.fade_out`, 0.3 s by default.
- A Unix socket path holds at most 107 bytes; the default one is far shorter.
- Instructions written by the user in `instructions_file` keep whatever they say about `working` until edited; the flag is then ignored.

## Alternatives considered

- **Keep the `working` flag as a hint**: two sources of truth, and the one that failed would still be there.
- **`mcp_tool` hooks calling a tool of the bridge**: no extra process, but the tool would be listed to Claude too, and the reference does not say how an array such as `background_tasks` is substituted into a tool's input.
- **A state file written by the hook and polled by the bridge**: simpler, but late by the polling interval, or busy polling.
- **`SubagentStart` and `SubagentStop`**: their coverage of background subagents is not documented, and `background_tasks` on `Stop` already tells whether work goes on.
