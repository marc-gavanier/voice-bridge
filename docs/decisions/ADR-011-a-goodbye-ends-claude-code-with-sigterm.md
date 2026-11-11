# ADR-011 — A goodbye ends Claude Code with SIGTERM

**Date**: 2026-11-11
**Status**: accepted

## Context

Ending a voice session meant leaving Mumla and closing the terminal by hand, which the speaker cannot do without a screen (#6). Saying it is over, in any words, should end everything: the bridge and the Claude Code session it serves, after a goodbye the speaker hears.

Claude Code documents no way for an MCP server, a channel or a hook to end the session that started it. Escape and Ctrl+C are keystrokes; `/exit` is typed by the user. What Claude Code does on a signal is not documented either. Tried on 2026-11-11 with Claude Code 2.1.322: an interactive session that receives SIGTERM exits within a second, with status 143, and its transcript is kept, so `claude --continue` resumes it.

## Decision

- The bridge exposes a second tool, `end_session`, next to `reply`, always loaded. Its `text` is the goodbye. Claude calls it when the speaker says the session is over, asking for confirmation when in doubt; the instructions say a mere stop ends the work, not the session.
- The goodbye joins the replies in order, as a reply that ends the session. Once it is played, and nothing is left to say, the conversation orders the bridge to leave when the playback ends. A noise over it keeps the ending; real words over it cancel it, and reach Claude as an interruption.
- Leaving sends SIGTERM to Claude Code. `claude-voice.sh` passes its own process ID to the bridge as `VOICE_BRIDGE_CLAUDE_PID`, in the `env` of the MCP server it declares: the script then `exec`s `claude`, which keeps that ID. Without the variable, the bridge logs that it has no Claude Code process to end and stays.
- `claude-voice.sh` allows `mcp__voice__end_session` without a permission prompt, as it does `reply`, since the speaker has no screen to answer one.

## Consequences

- A whole session ends by voice, and can be resumed later with `claude-voice.sh --continue`.
- The bridge relies on an observed, undocumented behaviour of Claude Code: a release that handles SIGTERM differently would break it, without any test noticing.
- The bridge ends with Claude Code, when its standard input closes; this, and the goodbye being heard in full before Mumble disconnects, are to be checked on a live session.
- The tool is offered even when the bridge was started otherwise than by `claude-voice.sh`; it then says goodbye and leaves the session open.
- While a stop is in force, the stop hook refuses `end_session` like any other tool but `reply` and `TaskStop`.

## Alternatives considered

- **Walking up the process tree to find `claude`**, through `/proc`: no change to the launcher, but the bridge runs under `with-cuda.sh` and `uv run`, so it would guess its ancestor by name, and could end a Claude Code session it was not started by.
- **A keyword recognised by the bridge itself**, such as the end route of the acknowledgements: ruled out in #6. A phrase said in passing would cut the session too abruptly, and Claude could not ask for confirmation.
- **Asking the speaker to close the terminal**: what #6 sets out to avoid.
