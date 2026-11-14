# ADR-026 — Words the acknowledgement answers bring no hold music

**Date**: 2026-11-15
**Status**: accepted, amends [ADR-014](ADR-014-claude-codes-hooks-tell-when-claude-works.md)

## Context

[ADR-014](ADR-014-claude-codes-hooks-tell-when-claude-works.md) counts Claude as working from the moment the speaker's words are forwarded, and starts the hold music `hold_music.delay` after any voice still playing. The instructions tell Claude not to reply when the acknowledgement already fully answers the message, such as « Je t'entends. » after « Tu m'entends ? », or « Avec plaisir. » after a thank-you. Claude then ends its turn without a word, but the music had already been scheduled: on 2026-11-15 at 00:09, « Est-ce que tu m'entends ? » got « Oui, je suis là. », then two seconds of music, until the `Stop` hook told the bridge that Claude was idle four seconds after the words were forwarded.

The log of that night shows no `busy` from the `UserPromptSubmit` hook for a message pushed by the channel: only the `Stop` hook tells the bridge about such a turn, so nothing else brings the music back.

## Decision

- A route of the language file can be marked `answers`, like `stops` and `greets`: its acknowledgement fully answers the speaker. Presence, thanks and compliment are marked, in all nine languages, and a test holds that only they are.
- The meaning of each transcription carries the flag, and the transcription event tells turn taking whether its acknowledgement answers it.
- Forwarding such words leaves Claude's work as it was: no music if Claude was idle, the music kept if Claude was already at work. Only words that reach Claude alone, with an acknowledgement played, and not said over Claude's voice, count: words said in pieces may mean something else together, words without an acknowledgement still need a reply, and after an interruption Claude says again what was not heard.

## Consequences

- « Tu m'entends ? », a thank-you or a compliment no longer bring two seconds of music for nothing.
- A message routed to one of these routes that asks for real work brings no music while Claude works, unless a hook says Claude is busy or Claude was already at work. The routes are prudent and their examples close, so this should stay rare; the utterance events tell how often it happens.
- A reply Claude still sends to such words is voiced as usual, and no music follows it.

## Alternatives considered

- **Cancel the music when the bridge learns the route**: the shell knows the route only once it chooses the acknowledgement, after the domain has scheduled the music, so the domain would need a second event to undo what it just decided.
- **A longer `hold_music.delay`**: delays the music of every real wait to save it on a few messages.
- **Let Claude tell the bridge it will not reply**: the kind of rule Claude must follow that ADR-014 set aside.
