# ADR-019 — The bridge announces only two or more tasks at work

**Date**: 2026-11-14
**Status**: accepted, partly supersedes [ADR-016](ADR-016-the-bridge-keeps-and-speaks-the-board-of-agents.md) for the announcements

## Context

[ADR-016](ADR-016-the-bridge-keeps-and-speaks-the-board-of-agents.md) has the bridge say each change of the agents at work: « Un agent au travail. », « Un agent a terminé, il en reste deux. », « Plus aucun agent au travail. ». In use, most changes concern a single agent ([#44](https://github.com/marc-gavanier/voice-bridge/issues/44)), and for one agent the hold music already tells that Claude works ([ADR-014](ADR-014-claude-codes-hooks-tell-when-claude-works.md)): the announcement repeats it, stops the music and talks over a wait that needed no words. The end of the last agent is told by Claude itself, which reports its result. What the speaker cannot hear from the music is how much work goes on at once.

## Decision

- Turn taking announces a count of agents at work only when it is two or more, each time it changes, going up or down: from one to two, from three to two, from two to three. A count of one or none is never said.
- A count that falls below two while an announcement still waits for silence drops it, so that a stale count is never said.
- The announcement is the count alone, in words of tasks rather than agents: each language's `announcements` table has one sentence for two to five tasks in progress and one for more than five, such as « Deux tâches en cours. » and « Plus de cinq tâches en cours. ». The sentences for one agent, for an agent finished with others left and for none left are gone, and `AgentsChanged` and `Announce` no longer tell a finished agent apart.

## Consequences

- With one agent at a time, the speaker hears only the hold music, and Claude's own report when it ends.
- With several, the speaker hears the count each time it changes, and « Deux tâches en cours. » after « Trois tâches en cours. » tells that one finished, without saying so.
- Going from two to one says nothing: the speaker learns that a task finished from Claude's report, and that one is left from the music going on.
- The sentences change, so the bridge voices them again at its first start, and caches them by text as before; the old clips stay unused in `cache_directory/announcements`.
- The word « agent » is no longer said aloud by the bridge: the counts speak of tasks, as Claude does.

## Alternatives considered

- **Keep announcing every change**: it repeats the hold music for one agent, which is the most common case.
- **Keep telling a start from an end**: « une tâche a terminé, il en reste deux » says more, but doubles the sentences for what the change of count already tells.
- **Announce the end of the last agent**: Claude reports its result, and the music stops when nothing is left to do.
