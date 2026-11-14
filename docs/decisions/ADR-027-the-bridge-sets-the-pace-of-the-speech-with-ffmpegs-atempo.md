# ADR-027 — The bridge sets the pace of the speech with FFmpeg's atempo

**Date**: 2026-11-15
**Status**: accepted, supersedes [ADR-018](ADR-018-the-speech-server-sets-the-pace-of-the-speech.md)

## Context

[ADR-018](ADR-018-the-speech-server-sets-the-pace-of-the-speech.md) sent `speech.speed` to the speech server, and vLLM-Omni stretched Voxtral's audio with librosa's phase vocoder. In a listening test on 2026-11-15, the same sentences at 1.2 sounded robotic stretched that way, and right stretched with FFmpeg's `atempo` filter.

`atempo` overlaps and adds pieces of the waveform where they match best, which keeps the pitch and the transients of speech. FFmpeg's documentation gives it a tempo from 0.5 up, and warns that above 2.0 it skips samples rather than blend them, advising a chain of several filters for that. The bridge already has FFmpeg in process: PyAV, which faster-whisper uses to decode audio files ([ADR-021](ADR-021-claude-plays-audio-files-from-one-directory.md)), ships FFmpeg 8.1 with its filters, `atempo` among them, and runs a filter graph on frames in memory.

The bridge resamples the server's audio, 24 kHz for Voxtral, to Mumble's 48 kHz with soxr.

## Decision

- The bridge no longer sends `speed` to the speech server. The speak ability asks a `Stretch` port, `(pcm, rate, factor) -> pcm`, to pace each sentence at the rate the server returned it, before resampling it to 48 kHz. The voice entry point plugs in `atempo`, run by PyAV, now a direct dependency.
- At 1.0, and for empty audio, the stretch returns the audio as it is, without building a filter graph.
- `speech.speed` stays the setting, 1.0 by default, but accepts 0.5 to 2.0 only: the range one `atempo` filter covers without skipping samples. A value outside it stops the start.
- The method, `atempo`, is part of the key of the cached acknowledgements and announcements, so those stretched by the server are voiced again, and it is named in the run's attributes as `voice_bridge.speech.pace`.
- Once the acknowledgements and announcements are recorded, each cache removes the clips this start did not ask for, and only files named as the cache names them.

## Consequences

- The pace is the same whatever the speech server: one that ignores `speed`, or one that refuses it when streaming, as vLLM-Omni does, now speaks at `speech.speed` too. Streaming the synthesis, which [ADR-023](ADR-023-the-first-sentence-is-voiced-from-its-first-clause.md) set aside partly for that reason, no longer conflicts with the pace, though the stretch would then run on chunks.
- The bridge spends CPU on each sentence: about 4 ms for 10 s of speech at 24 kHz, measured on the workstation, against seconds of synthesis.
- Stretching at 24 kHz processes half the samples it would at 48 kHz, and the resampler then smooths what the stretch leaves.
- The stretched audio lasts its duration divided by the speed within about 50 ms, measured from 0.25 s to 6 s; a property test holds it within 0.1 s. Audio shorter than about 40 ms comes out empty, far below any sentence Voxtral voices.
- A config with a speed below 0.5 or above 2.0, valid under ADR-018, stops the start until it is changed.
- The first start after this change voices every acknowledgement and announcement again, then removes the clips of the old key; clips orphaned by earlier changes of voice, gain or wording go too.

## Alternatives considered

- **Keeping the server's phase vocoder**: no work on the bridge, but it sounded robotic at the pace wanted.
- **Rubber Band**, through FFmpeg's `rubberband` filter or its own library: a library made for stretching, but PyAV's FFmpeg is not built with it, so it would need a system library or another package, for a gain not heard in the test; set aside for now.
- **Chaining `atempo` filters** to keep 0.25 to 4.0: more code and a quality FFmpeg itself warns about, for paces nobody listens to.
- **FFmpeg as a subprocess**: the same filter, but a process and a WAV round trip per sentence, when PyAV runs it in memory.
- **Stretching at 48 kHz, after resampling**: twice the samples for the same result.
