# ADR-016 — The bridge keeps and speaks the board of agents

**Date**: 2026-11-13
**Status**: accepted, partly supersedes [ADR-014](ADR-014-claude-codes-hooks-tell-when-claude-works.md) for the socket's messages

## Context

Out on a run, the speaker hands work to Claude, which hands it to background agents and stays available to talk ([#3](https://github.com/marc-gavanier/voice-bridge/issues/3)). What a dashboard of agents gives on a screen has to be given by voice: what runs, what finished, and what came of it. Claude cannot be the only source: it forgets what it handed out once its context is summarized, and relying on it to report every start and end is the kind of rule it failed to follow before ([ADR-014](ADR-014-claude-codes-hooks-tell-when-claude-works.md)).

Claude Code 2.1.325, tried headless on 2026-11-13 with a hook logging every input, gives what is needed:

- `SubagentStart` carries `agent_id` and `agent_type`; `SubagentStop` adds `last_assistant_message`, `background_tasks` and `session_crons`.
- For a background agent, its entry in `background_tasks` has the agent's `agent_id` as its `id`, with `type`, `status`, `description` and `agent_type`; on its own `SubagentStop`, the finishing agent is still listed as running. A foreground agent never appears there.
- For a background agent the order is `SubagentStart`, `Stop` with the task running, `SubagentStop`, `UserPromptSubmit` with a `<task-notification>` prompt, then `Stop`.
- The [hooks reference](https://code.claude.com/docs/en/hooks.md) warns that `SubagentStop` also runs for Claude Code's internal agents, such as prompt suggestions and `/btw`, with an empty `agent_type` or the session's own agent name.

The speaker does not want to hear what each agent does, only that work goes on and how much.

## Decision

- `claude-voice.sh` registers `voice-bridge-activity-hook` on `SubagentStart` and `SubagentStop` as well, still as an async command hook.
- The hook tells the bridge one JSON object per connection, on one line, discriminated by `kind`: `busy`, with the background tasks' ids and descriptions; `idle`; `started`, with the agent's id and type; `finished`, with its id, type, last message and the background tasks. Both ends share the pydantic models, and the bridge ignores a line that does not match them. A line may hold up to 1 MiB, enough for a last message. Busy and idle are decided as [ADR-014](ADR-014-claude-codes-hooks-tell-when-claude-works.md) set out.
- The board is a pure domain in the conversation feature: the agents at work, each with its id, type, start time and the description of its task once a background task of the same id tells it, and the twenty latest finished, each with its end time and last message. An agent started without a type, or already at work, and an agent finishing without having been seen starting, change nothing: that leaves out Claude Code's internal agents without knowing the session's agent name.
- Each change of the agents at work becomes an `AgentsChanged` event of turn taking, with the number at work and whether one finished. Turn taking keeps the latest one in a single slot and answers it with an `Announce` command once the conversation is quiet: no speaker heard, nor beginning some words, nothing of Claude's reply left to voice, no goodbye under way. Over the hold music, it stops the music first and waits for it again.
- The shell plays a clip voiced at startup: each language's TOML file has an `announcements` table, with a sentence for one to five agents at work, for one agent finished with one to five left, for more than five in both cases, and for none left, all voiced when Voxtral is ready and cached on disk under `cache_directory/announcements`, as the acknowledgements are. Only counts are said.
- The channel server gives Claude a `board` tool, with no input and a description in each language, that returns the board as JSON with the time now. `claude-voice.sh` allows it without asking, since it only reads.

## Consequences

- The speaker hears each agent start and finish, without Claude saying it and without Claude's voice or their own being cut, and Claude can answer « what is running? » at any time from the board.
- The announcement goes into the loudspeaker's queue after Claude's last sentence or the acknowledgement; turn taking does not know its length. A speaker who starts talking while it plays does not cut it, as with an acknowledgement, and an interruption that cuts Claude's voice drops an announcement queued behind it.
- Changes that come while someone speaks are said as one count, the latest: « un agent a terminé » may be replaced by « deux agents au travail » when another starts meanwhile. Claude still reports each result, from the notification Claude Code sends it.
- A foreground agent counts like a background one, but has no description, since it never appears in `background_tasks`.
- The board starts empty with the bridge: an agent started before it is never counted, and its end changes nothing.
- The board lives in memory: it is lost when the bridge stops, and holds at most twenty finished agents.
- Until Voxtral has voiced the announcements, a change is logged as `no announcement ready` and not said.
- The word « agent » is said aloud by the bridge only: the default instructions keep asking Claude never to speak of agents or delegation, so the counts are the one place the speaker hears of them, as Marc asked.
- The main agent may call `board` in a voice session: it is on the allow list of [ADR-015](ADR-015-the-main-agent-delegates-in-voice-sessions.md).

## Alternatives considered

- **Let Claude announce the agents**: it depends on Claude following an instruction, which [ADR-014](ADR-014-claude-codes-hooks-tell-when-claude-works.md) set aside for the hold music, and forgets after a summary.
- **Read the board from `background_tasks` on `Stop` only**: it tells neither the end of an agent with its last message nor a foreground agent, and comes only when the main agent ends a turn.
- **Synthesize each announcement when it is due**: no startup cost, but it waits for Voxtral, about a second, competes with Claude's sentences, and turn taking would have to tell the bridge's sentences from Claude's to know what an interruption cut.
- **Announce what each agent does**: the speaker asked not to hear it; the descriptions stay on the board for Claude to read when asked.
- **Queue every change**: a burst of agents starting would be read out one by one, where a dashboard shows only the current count.
- **Keep bare words and add more of them**: the last message and the tasks' descriptions do not fit a word, and a second socket would duplicate the listener.
