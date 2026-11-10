# ADR-009 — Smart Turn ends a sentence before the silence

**Date**: 2026-11-11
**Status**: accepted

## Context

A sentence ends after 0.8 s of silence. That silence is added to every turn before transcription can start, and a short pause mid-sentence while running still cuts a sentence in two (#4). Measured at home on 2026-11-10, a turn takes about 4 s from the end of a sentence to the first word heard, 0.8 s of which is this silence.

[Smart Turn v3.2](https://github.com/pipecat-ai/smart-turn), from the Pipecat project, is a model trained to tell from the audio, intonation included, whether a speaker has finished. It is small (8.7 MB for the CPU build), BSD 2-clause for code and weights, and runs on ONNX Runtime, already installed with faster-whisper. Its authors pair it with a voice activity detector such as Silero: after a short silence, they run it on the whole turn, up to its last 8 seconds, and run it again if speech resumes. They announce 10 to 65 ms per decision on a CPU and 96 % correct decisions in French for v3.0.

## Decision

- After a short pause (`hearing.short_pause`, 0.2 s), the ears ask Smart Turn whether the turn is finished, once per pause. Above `hearing.turn_threshold` (0.5, the reference value), the sentence ends at once. Otherwise it goes on, and the 0.8 s silence and the 30 s limit still end it as before.
- The rule stays in the pure hearing domain: the domain says when a check is due and closes the sentence on the answer; the ability calls the model between the two.
- The model file is downloaded from Hugging Face at a pinned revision and cached like the Whisper models. Its input features come from faster-whisper's feature extractor, after the same zero-padding at the start and normalisation as the reference code. On the test recording, they match the reference `transformers` features to 3·10⁻⁶ and give the same probabilities, so `transformers` is not needed.
- The setting `hearing.smart_turn` is off by default, so the change can be tried and compared on a real run before it becomes the default.
- Every decision is logged with its probability, the pause and the time saved against the silence rule, and every inference with its duration.

## Consequences

- A sentence can end 0.6 s sooner, and a pause mid-sentence no longer ends it unless Smart Turn judges the turn finished.
- Closing a sentence after 0.2 s of silence broke the guarantee that an interruption is never dismissed as too short, which relied on `barge_window < silence + barge_in`. Closing a sentence now forgets its voice in the barge-in window, so an interruption only counts the sentence in progress, and that setting rule is gone.
- The model runs in the listening loop, as Silero does: incoming audio waits during each decision, then is processed; nothing is lost. The log's stall lines and decision durations show what it costs.
- A wrong "finished" cuts a sentence that the next one completes, and Claude receives it in two parts. The threshold and the short pause are settings, to adjust from the logged probabilities.
- The 96 % were measured on French spoken calmly; nothing is known yet for speech while running.
- The first start with the setting on needs network access to Hugging Face.

## Alternatives considered

- **A shorter silence alone**: saves the same time, but cuts every pause mid-sentence, the opposite of what #4 asks.
- **Pipecat's `LocalSmartTurnAnalyzerV3`**: Pipecat brings its own pipeline, transport and process model; only the model is needed, as already decided for Silero.
- **`transformers` for the features**: what the reference code uses, but a large dependency for a log-mel spectrogram that faster-whisper already computes identically.
- **The GPU build of the model**: 32 MB and fp32; the CPU build already answers in tens of milliseconds, and the GPU is busy with Whisper and Voxtral.
