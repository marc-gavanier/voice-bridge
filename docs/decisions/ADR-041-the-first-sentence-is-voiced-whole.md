# ADR-041 — The first sentence is voiced whole

**Date**: 2026-11-18
**Status**: accepted, supersedes [ADR-023](ADR-023-the-first-sentence-is-voiced-from-its-first-clause.md)

## Context

[ADR-023](ADR-023-the-first-sentence-is-voiced-from-its-first-clause.md) cut the first sentence of a reply after its first clause, because the bridge then waited for the whole voice of a sentence before playing it, so the first sound grew with the length of the first sentence. Since [ADR-029](ADR-029-the-bridge-plays-the-voice-as-the-speech-server-streams-it.md), the bridge plays the voice as the speech server streams it, and ADR-029 kept the cut only until the traces told whether it still helped.

The traces of 423 turns, all streamed, tell it:

- The first sound of a reply comes 0.15 s in median after it is asked for, whatever the length of the first sentence.
- A first sentence cut at its comma gives its first sound in 0.150 s in median, against 0.150 s for one voiced whole: the cut saves nothing.
- Of the pieces voiced, 295 were cut at a comma and 2,887 were whole sentences.
- No gap was measured in the playback of the 412 cases measured.
- The first sentence is synthesized at least 2.2 times faster than it is played, so the playback does not catch up with the synthesis.

The cut still had a cost: one more piece, so one more request to the server, and an intonation Voxtral may close in the middle of a sentence that goes on, as ADR-023 expected.

## Decision

- Every sentence of a reply, the first one included, is cut on its final punctuation only and voiced whole.
- A sentence shorter than the shortest sentence, twelve characters, is still merged with the next one, so no piece but the last is a lone fragment.

## Consequences

- The first sentence keeps the intonation of a whole sentence.
- A reply asks the server for one piece fewer whenever ADR-023 would have cut its first sentence.
- The rules of the cut are gone from the speaking domain, with their tests and the four words they counted.
- If the server voices slower than the speech is played, as it might while Whisper shares the GPU, a long first sentence is no more exposed than any later one: the margin to watch stays the one of ADR-029.

## Alternatives considered

- **Keeping the cut**: it saves no time on the first sound since streaming, and costs a piece and an intonation that may close too early.
- **Cutting every sentence at its clauses**: it would add pauses and requests without saving any wait, which ADR-023 already set aside.
