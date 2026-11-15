# ADR-023 — The first sentence is voiced from its first clause

**Date**: 2026-11-14
**Status**: accepted, amended by [ADR-029](ADR-029-the-bridge-plays-the-voice-as-the-speech-server-streams-it.md), which streams the voice it set aside

## Context

The bridge voices a reply sentence by sentence, and plays each one while the next is synthesized: only the first sentence is waited for. Measured on the runs of 2026-11-12 to 2026-11-14, Voxtral took 0.80 s in median to voice the first sentence, about 0.26 s of compute per second of speech, and that sentence lasted 2.95 s in median, so the time to the first audio grows with the length of the first sentence. The research gathered in #44 found the same with vLLM-Omni: smaller first chunks lower the time to the first audio.

## Decision

- The first sentence of a reply is cut after its first comma, semicolon, colon or dash followed by a space once the words before it number at least four; later sentences are cut as before, on their final punctuation only.
- A first piece shorter than the shortest sentence, twelve characters, is merged back with the rest, and a rest shorter than that is merged with the next sentence, so no piece but the last is a lone fragment.
- Joined with a space, the pieces give back the reply, single spaced.

## Consequences

- The first audio waits for the first clause rather than the whole first sentence; the rest of that sentence is synthesized while the first clause plays.
- Voxtral voices the first clause on its own, so its intonation may close where the sentence goes on; this is judged by ear on the next runs.
- The cut follows the Western comma, semicolon, colon and dashes only: a reply in Chinese or Japanese still waits for its whole first sentence.

## Alternatives considered

- **Asking Claude for a short first sentence**: the instructions already ask for short sentences, yet the first one still lasts 2.95 s in median; a cut in the bridge does not depend on Claude.
- **Streaming Voxtral's audio as PCM chunks**: saves the time to the first audio whatever the sentence, but changes the speech client and the playback, and vLLM-Omni refuses a `speed` other than 1.0 when streaming ([ADR-018](ADR-018-the-speech-server-sets-the-pace-of-the-speech.md)).
- **Cutting every sentence at its clauses**: only the first sentence is waited for; cutting the others would add pauses between pieces without saving any wait.
