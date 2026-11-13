# ADR-015 — The main agent delegates in voice sessions

**Date**: 2026-11-13
**Status**: accepted

## Context

Out on a run, most of a voice session was hold music: Claude did every task itself, so each request kept the speaker waiting for the whole task, tests, mutation runs and documentation included, and nothing else could be asked meanwhile (#3). What the speaker needs is to hand work out and keep talking, as an agent dashboard allows on a screen.

The instructions already allowed Claude to hand work to sub-agents, but an instruction is not enough: the `working` flag of ADR-014 failed because it relied on Claude applying it. Claude Code's `PreToolUse` hook can refuse a tool call with a reason Claude reads, and `voice-bridge-stop-hook` already used it to refuse tools after a stop (ADR-010).

Tried on 2026-11-13 with Claude Code 2.1.325 (#3): on `PreToolUse`, `agent_id` and `agent_type` are absent from the main agent's calls and present on any subagent's, in the foreground or the background; every other field is the same. The presence of `agent_id` is the only marker, and it is enough.

## Decision

- In a session started by `claude-voice.sh`, the main agent only talks and hands out work. The instructions of the nine languages tell it to hand every task that is not instant to a background agent, end its turn at once, and tell the result when it comes back, never mentioning agents to the speaker.
- The `PreToolUse` hook refuses the main agent every tool but `mcp__voice__reply`, `mcp__voice__end_session`, `Agent`, `SendMessage`, `TaskStop`, `ListAgents`, `Read`, `Grep`, `Glob`, `ToolSearch`, `Skill`, `Workflow`, the scheduling tools `ScheduleWakeup`, `CronCreate`, `CronList` and `CronDelete`, and the task list tools `TaskCreate`, `TaskGet`, `TaskList`, `TaskUpdate` and `TodoWrite`: speaking, starting and steering agents, reading, loading deferred tools such as `SendMessage` and `TaskStop`, loading a skill's instructions, orchestrating a workflow, scheduling a wakeup as `/loop` does, and keeping a list of things to do; none of them works on files or runs commands. `Monitor`, which runs a command, and `AskUserQuestion`, a dialog on a screen nobody looks at on a run, stay refused. A call carrying an `agent_id` is a subagent's and keeps every tool. The refusal's reason, `delegation_refusal` in each language pack, tells Claude to hand the task to a background agent, end its turn and stay available to talk.
- The rule holds in every session the launcher starts, even when the speaker types, with no switch: working directly means starting Claude Code without the launcher.
- One hook enforces both refusals: `voice-bridge-stop-hook` becomes `voice-bridge-tool-hook`. A stop is checked first, for every agent, then delegation, for the main agent only, so after a stop Claude reads the stop's reason and only `reply` and `TaskStop` run. Following ADR-005, the delegation rule is a pure function of the `conversation` domain, the stop rule stays in `understanding`, the entry point wires both, and the hook's input and its refusal, which both features read and write, move to a new library, `libraries/claude_code`.
- The allow lists of the main agent and of a stop are constants of the entry point, side by side, so either is adjusted in one place.

## Consequences

- The speaker can keep talking while work runs, and Claude delegates whether or not it follows the instructions: a refused tool tells it to delegate.
- A task the main agent would have done in one command now costs an agent's start; reading stays allowed so that Claude can answer quick questions from a file itself.
- The main agent loses every other tool, `Bash`, `Edit`, `Write`, `Monitor` and `AskUserQuestion` among them. On Linux, Claude Code has no separate `Grep` and `Glob` by default and searches through `Bash`, so the main agent reads known files and delegates every search; whether that hinders will be seen in use.
- Grep and Glob are absent by default on Linux, where Claude searches with `Bash`: there, the main agent reads files it knows and delegates any search.
- A future Claude Code that marks the main agent's calls with an `agent_id`, or stops marking a subagent's, breaks the rule silently: every tool would be allowed, or refused to everyone. The fields are documented as common hook input, and the experiment of #3 is the check to repeat after an upgrade.
- Still one `uv run` per tool call, about 0.2 s, as in ADR-010.

## Alternatives considered

- **Instructions alone**: what failed for the `working` flag.
- **A sibling entry point registered next to the stop hook**: each feature would keep its own hook, but every tool call would start two `uv run` processes, and when both refuse, which reason Claude reads would depend on how Claude Code merges two denials, not on the bridge.
- **Moving the stop's refusal into `conversation`** with delegation, in one pure function: one feature would own every refusal, but detecting a stop belongs to `understanding`, and the move would only rename code that works.
- **Claude Code's own permission rules**, `--disallowedTools` in the launcher: they apply to the session's subagents too, which would lose the tools they need.
- **A switch to work directly by voice or at the keyboard**: a second mode to keep in mind and to test; starting Claude Code without the launcher already gives it.
