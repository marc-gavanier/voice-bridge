# ADR-035 — Silero, Smart Turn's features and audio files no longer come from faster-whisper

**Date**: 2026-11-16
**Status**: accepted, amends [ADR-009](ADR-009-smart-turn-ends-a-sentence-before-the-silence.md) for Smart Turn's features

## Context

ADR-034 makes every step of listening swappable alone, and its first change cuts what faster-whisper lent to the other steps (#80):

- Voice detection loaded the copy of Silero VAD v6 shipped inside faster-whisper's package, an export whose state is split in two.
- Smart Turn's log-mel features came from faster-whisper's `FeatureExtractor`, as ADR-009 chose because faster-whisper was already there.
- Hold music and the clips of the `play` tool were decoded with faster-whisper's `decode_audio`, a thin layer over PyAV.

Replacing Whisper would have broken all three. The behaviour had to stay the same.

## Decision

- **Silero** comes from its own repository: `silero_vad.onnx` at the commit of [snakers4/silero-vad](https://github.com/snakers4/silero-vad) that added the v6 models, checked against its SHA-256 and cached by [pooch](https://www.fatiando.org/pooch/). The official model takes one state tensor and the sample rate; on the test recording it gives the same probabilities as faster-whisper's copy, window by window, and the session keeps faster-whisper's options.
- **Smart Turn's features** come from `transformers`' `WhisperFeatureExtractor`, which Smart Turn's reference code uses, after the same padding at the start and normalisation as before. On the test recording they match faster-whisper's to 3·10⁻⁶ and give the same probability.
- **Audio files** are decoded with PyAV directly, with the same steps as `decode_audio`: invalid frames skipped, timestamps ignored, mono 16-bit PCM at the rate asked, resampler flushed. The output is byte for byte the same.
- faster-whisper is imported only where the speech recognizer is built, the voice entry point; an architecture test holds it.

## Consequences

- Each of the three steps can change without Whisper, and Whisper without them.
- The first start needs network access to GitHub for Silero, 2 MB, as it does to Hugging Face for Smart Turn and MiniLM. Silero is cached in pooch's cache, `~/.cache/pooch`, outside the Hugging Face cache that the CI keeps between runs, so the CI downloads it each time.
- `transformers` adds about 60 MB, with `regex`, `safetensors` and `typer`, and about two seconds to the start; without PyTorch it logs one advisory line when imported. `pooch` adds `requests`.

## Alternatives considered

- **The `silero-vad` package**: Silero's own, but it requires PyTorch even for its ONNX model.
- **Hugging Face's client for Silero**, as for Smart Turn: Silero publishes no model on the Hub, and the copies there are other people's exports.
- **Silero v6.2**, the latest model: it changes the probabilities, by up to 0.54 on the test recording, so it waits for its own change.
- **Whisper's log-mel spectrogram written by hand with NumPy**: no new dependency, but a copy of an algorithm that `transformers` maintains as the reference Smart Turn was trained with.
- **`librosa` for the features**: its filters are Whisper's, but it brings Numba and SciPy, and the Whisper steps around them would still be ours.
