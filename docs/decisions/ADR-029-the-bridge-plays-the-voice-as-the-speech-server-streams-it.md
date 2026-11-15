# ADR-029 — The bridge plays the voice as the speech server streams it

**Date**: 2026-11-15
**Status**: accepted, amends [ADR-023](ADR-023-the-first-sentence-is-voiced-from-its-first-clause.md)

## Context

The bridge asked Voxtral for the whole WAV of a sentence and played it once it had all arrived, so the wait before a reply's first sound grew with the length of its first sentence; [ADR-023](ADR-023-the-first-sentence-is-voiced-from-its-first-clause.md) shortened that sentence, and set streaming aside because vLLM-Omni refused a `speed` when streaming. Since [ADR-027](ADR-027-the-bridge-sets-the-pace-of-the-speech-with-ffmpegs-atempo.md), the bridge sets the pace itself, so that reason is gone.

vLLM-Omni 0.32 streams the audio of `/v1/audio/speech` as raw PCM when asked for `"response_format": "pcm"`, `"stream": true` and `"stream_format": "audio"`, and names the rate in an `X-Audio-Sample-Rate` header: 24 kHz, 16-bit mono for Voxtral. Its first piece holds 0.4 s of audio, the next ones follow every 0.1 s or so, and later pieces grow to 1.4 s.

Measured on 2026-11-15 against the running server, `fr_female`, each sentence asked twice in each mode, medians in seconds:

| Characters | Audio | Whole WAV | First streamed piece | Whole stream | Gain |
|---|---|---|---|---|---|
| 9 | 0.56 | 0.20 | 0.16 | 0.22 | 0.04 |
| 26 | 1.44 | 0.40 | 0.14 | 0.38 | 0.26 |
| 49 | 2.96 | 0.81 | 0.15 | 0.89 | 0.66 |
| 111 | 5.12 | 1.41 | 0.15 | 1.35 | 1.27 |
| 215 | 10.88 | 2.74 | 0.16 | 2.75 | 2.58 |

The first piece comes in 0.15 s whatever the length, a median gain of 0.66 s, and the whole stream takes as long as the whole WAV. The streamed audio is continuous: across the boundaries of the pieces, the jump between two samples stays below the 99th percentile of the jumps within the audio, and no run of silence is longer than four samples. Its length matches the WAV's within the variation between two requests, since Voxtral samples each one. At a speed of 1.2, each piece arrived at least 0.23 s before the playback of the pieces before it would have run out.

FFmpeg's `atempo` gives back its output one input frame late: pushed as one 0.4 s frame, the first piece came out empty, while in 20 ms frames 0.28 s of the 0.33 s it stretches to came out at once. soxr's `ResampleStream` holds back about 10 ms.

## Decision

- Each sentence of a reply is asked for as a raw PCM stream, at the rate the server names, or 24 kHz, the rate of OpenAI's raw PCM, when it names none. A sample cut between two pieces waits for the next one.
- Each sentence gets its own `atempo` graph, fed in 20 ms frames, its own soxr `ResampleStream` to 48 kHz and the gain, piece by piece; both are flushed when the stream ends. The `Pacing` port of the speak ability gives a pace with `push` and `end`, replacing the `Stretch` port.
- Turn taking receives a `Voiced` event for each piece, with its audio and duration, and `Synthesized` once the whole voice has arrived. The first piece follows the rules the whole voice followed: it waits while the speaker is heard, stops the hold music and makes the reply heard. Each later piece plays after the pieces before it, or from its arrival if they have run out. The sentence counts as being synthesized until its voice ends, so an interruption saves it whole, as it saved a sentence playing; the next sentence is asked for only then, so the server voices one sentence at a time, as before.
- Whenever turn taking drops a synthesis before its voice ends, on an interruption, a stop, or a first piece arriving while the speaker is heard, it orders `CancelSynthesis`, and the shell cancels that sentence's task, which closes the stream.
- A stream that fails after some pieces keeps what was played and moves on to the next sentence, as a failed synthesis does; one that ends without a piece is skipped the same way.
- The acknowledgements and announcements, voiced once at startup and cached, are still asked for whole, as are recordings played with `play`, which arrive as one piece.
- Each sentence's trace has a `first audio` step, from the order to the first piece, and a `synthesis` until the whole voice; its `playback` starts with the first piece and lasts as long as all of them. The log adds `first audio in … s` and `synthesis … cancelled`, and keeps `voice in … s for … s of speech` for the whole voice.

## Consequences

- A reply's first sound no longer waits for its first sentence: about 0.15 s after it is asked for, plus 20 ms of `atempo` and 10 ms of resampling, against 0.8 s in median before. The cut of the first sentence after its first clause ([ADR-023](ADR-023-the-first-sentence-is-voiced-from-its-first-clause.md)) now saves little; it stays until the traces tell whether it still helps.
- A barge-in stops the server's work on the sentence it cut, rather than letting it finish a voice nobody will hear.
- If the server voices slower than the speech is played, as it might while Whisper shares the GPU, the playback runs out between two pieces: Mumble's sender pads with silence for a few frames, then ends the transmission, and the speaker hears a gap. The margin measured, 0.23 s per piece at a speed of 1.2, is the one to watch in the `first audio` and `synthesis` steps.
- The request uses vLLM-Omni's `stream` field: a server that refuses it, or does not stream raw PCM, voices no sentence of a reply, and the log says `no voice for …` for each. The acknowledgements, asked for whole, still play.
- Each piece is one event through turn taking, ten to fifteen for a long sentence instead of one.

## Alternatives considered

- **Keeping the whole WAV**: no change, but a long first sentence keeps the speaker waiting up to 2.7 s for its voice.
- **The server-sent events of `stream_format: "sse"`**: the same pieces in base64 inside JSON events, more bytes and parsing for nothing the raw stream lacks.
- **vLLM-Omni's WebSocket speech endpoint**: it also takes the text as it is written, but it is a protocol of its own, outside OpenAI's speech API that the bridge speaks.
- **Asking for the next sentence while the current one streams**: two requests share the GPU and both slow down, while the stream already arrives about four times faster than real time.
- **A playback-finished event from the speaker** to end a sentence whose length is unknown: the length of each piece is known when it arrives, so the end of the voice follows from them without a new port.
- **A setting to turn streaming off**: the gain holds for every length measured, so it would only keep a path nobody uses.
