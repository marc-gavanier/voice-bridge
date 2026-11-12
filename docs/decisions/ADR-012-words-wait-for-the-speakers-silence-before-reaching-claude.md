# ADR-012 — Words wait for the speaker's silence before reaching Claude

**Date**: 2026-11-12
**Status**: accepted

## Context

On the run of 2026-11-11, outdoors over 4G, the speaker thought aloud and paused mid-sentence. Smart Turn ([ADR-009](ADR-009-smart-turn-ends-a-sentence-before-the-silence.md)) judged 299 of 329 turns finished, after 0.40 to 0.45 s of silence with `short_pause = 0.4`, and it is confident on French hesitations: 0.90 on « Alors... », 0.95 on « Par exemple, avec le module... ». Raising `hearing.turn_threshold` would have spared few of the cuts.

Each sentence was pushed to Claude at once, and its acknowledgement played 0.5 s after the transcript unless the speaker spoke again. At least 48 sentences were followed within 6 s by words that continued them, such as « Donc, je voudrais faire... » then « un ticket parmi ceux qui restent le plus facile. ». The speaker went on about 0.9 s after the end of their words, and within about 1.6 s nine times out of ten, measured roughly from the utterance lengths; the acknowledgement fell at about 1.05 s, over the next words. Claude, which answers in about 3 s, also answered the first piece while the speaker said the rest: the 21 interruptions of the run were all the speaker's own voice cutting such a reply.

Voice agent frameworks wait for the same reason: [LiveKit](https://docs.livekit.io/reference/agents/turn-handling-options/) holds a turn between a minimum and a maximum endpointing delay, 0.5 s and 3 s by default, 0.3 s and 2.5 s with its audio turn detector, and can adapt the delay to the pauses of the session.

## Decision

- Transcribed words wait in the turn-taking domain until the speaker has kept silent for `hearing.settle`, 1.2 s by default, counted from the end of their voice: the listener tells the conversation when the voice of each utterance ended, before transcribing it, so the silence Smart Turn and Whisper already took, about 0.6 s, is not waited again. Words said within that silence are joined to them, separated by a space, and reach Claude as one message; Claude's reply waits as well.
- The domain counts the utterances started and not yet transcribed, so words still being transcribed when the speaker goes on are held back too.
- A sound dismissed as too short now reaches the conversation as its own event, so that a noise after a pause cannot hold the words back forever. Unlike a transcript filtered as noise, it never resumes a paused reply: a click dismissed while Whisper still transcribes the words that interrupted would resume the reply too early and send those words unmarked, as #24 found.
- The acknowledgement plays when the words are pushed, under the same rules as before: none while Claude talks or after one already played since Claude last replied. `hearing.settle` replaces `hearing.acknowledgement_delay`.
- A message joined from several pieces is logged with their number.
- A sound dismissed as too short does not move the end of the voice: a click after the words cannot delay them.

## Consequences

- Claude receives whole thoughts, and neither the acknowledgement nor a reply falls in a pause shorter than `hearing.settle`.
- Every reply comes about 0.6 s later than before, a stop included, since the stop flag is set when the words are pushed; the acknowledgement comes about 1.2 s after the end of the voice, about as late as the former 0.5 s after the transcript. Measured on the run, the end of speech to the reply's voice took 5.3 s in median, 3.1 s of which was Claude.
- A pause longer than `hearing.settle` still cuts a thought in two; the log's `joined` and `forwarded` lines tell whether to lengthen it.

## Alternatives considered

- **Delay only the acknowledgement**: leaves Claude answering half a sentence, which caused the interruptions of the run.
- **A higher Smart Turn threshold or a longer short pause**: the model is confident on hesitations, so a higher threshold spares few cuts, and a longer pause delays every turn without covering pauses longer than a second.
- **Hold words that end with an ellipsis or a connecting word longer**: cheap, but Whisper often closes an unfinished sentence with a full stop; it may come on top of this decision once runs show what the fixed wait misses.
- **An adaptive wait, such as LiveKit's dynamic mode**: learns the speaker's pauses, at the cost of state and tuning; a fixed setting comes first, to be measured.
