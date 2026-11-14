# ADR-018 — The speech server sets the pace of the speech

**Date**: 2026-11-14
**Status**: accepted

## Context

Voxtral speaks at one pace, slower than a listener used to the voice wants. The OpenAI speech API, which the bridge speaks ([README](../../README.md#configure)), defines a `speed` field from 0.25 to 4.0 on `POST /v1/audio/speech`. vLLM-Omni implements it for Voxtral by stretching the generated audio with librosa's phase vocoder, which keeps the pitch, and skips the stretch at exactly 1.0. It refuses any other speed when the audio is streamed, which the bridge does not do yet.

## Decision

- `speech.speed`, 1.0 by default, is sent as `speed` with every synthesis. Values outside 0.25 to 4.0, the range of the API, stop the start.
- The speed is part of the key of the cached acknowledgements and announcements, so a new speed voices them again instead of mixing two paces.

## Consequences

- At the default, the server skips the stretch and the speech is the same as before.
- Any server with the OpenAI speech API, such as Kokoro-FastAPI, takes the same setting; one that ignores the field speaks at its own pace.
- Streaming the synthesis, to start speaking sooner, would need the speed back at 1.0 with vLLM-Omni, or a stretch on the bridge's side.
- A phase vocoder smears transients a little; the pace that sounds right is found by ear, not measured.

## Alternatives considered

- **Stretching the audio in the bridge**, with librosa or audiotsm: works with every server and with streaming, but adds a dependency and CPU work on every sentence for what the server already does.
- **Resampling**: faster and simpler, but raises the pitch with the pace.
