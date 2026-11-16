# ADR-038 — The transport pulls what it sends from one player

**Date**: 2026-11-16
**Status**: accepted, details the audio output of [ADR-035](ADR-035-every-brick-of-the-voice-chain-is-swappable-behind-a-port.md)

## Context

ADR-035 puts one player behind a port, mixing the bridge's voice, the clips of `play` and the hold music, the only writer to the transport's sending side, and giving the signal it played as the reference for echo cancellation (#35). Until #86, the voice and the hold music each wrote to the transport's `play`, which queued the audio in pymumble's `PcmBuffer`, 600 s long, and the conversation's `stop` cleared it. Nothing mixed: the hold music's fall and the voice that followed it were only queued one after the other. pymumble pulls a frame of 20 ms from its audio source on each tick of its own clock, `AudioSource.read(size)`; discord.py pulls the same way, while LiveKit takes frames pushed at its pace.

The issue asks for no change in what the speaker hears: the music falls over `hold_music.fade_out` before the reply's voice, as the README says.

## Decision

- **The transport pulls.** Its port loses `play` and `stop`; `carry` takes an `Outgoing` port, which gives the next frame of a size the transport asks for, or nothing until a whole frame is ready. Mumble hands it to pymumble as the audio source of each connection. A transport that takes pushed frames runs its own loop and pulls the same port.
- **One player owns the mix**, in the `mix` ability of the speaking feature, and is that `Outgoing` port. Producers play through a channel, one per layer: the voice layer for the voice, the acknowledgements, the announcements and the clips, which turn taking already orders as sentences of a reply; the music layer for the hold music. Each producer keeps its own `Speaker` port, since features never import each other; the entry point hands each the channel of its layer.
- **The mix is pure**, in the ability's `domain`, with the standard library only. A sound added to a layer that still plays follows it; a sound on an idle layer waits for everything already queued, which keeps today's order, the fall then the voice; layers that overlap are summed sample by sample and clipped at full scale. Stopping drops every layer, as clearing the buffer did. Changing how the layers meet, such as the music fading under the voice, changes this rule alone.
- **The reference is each frame pulled**, handed to a `Reference` port with the time of the bridge's clock at which the transport took it: what was sent, when it was sent, mixed. Until #35 listens to it, nobody does.

## Consequences

- Mixing happens as a frame leaves, so a sound queued late still mixes with what has not been sent yet, and the reference is exact without guessing what the transport still holds.
- The queue has no bound, where pymumble's buffer held 600 s; `clips.longest` and the hold music's one second ahead keep it short.
- Summing in pure Python costs about 0.12 ms per frame of 20 ms with both layers, measured on the development machine, on the event loop. A layer keeps its position in its audio rather than slicing it, so a long clip costs no more per frame.
- The recorder, which sends nothing, gives a silent `Outgoing`.

## Alternatives considered

- **The player pushing frames to the transport on its own clock**, keeping `play`: two clocks pacing the same audio, a lead to choose between gaps and latency, and a reference that guesses when each frame left.
- **The player writing ahead into the transport's buffer**, as the producers did: what is written can no longer be mixed with a sound that comes later, and the reference again guesses the timing.
- **A layer for the clips**: turn taking plays them in turn with the sentences of a reply, so a layer of their own would never overlap the voice.
- **Mixing with NumPy in an implementation**: faster, but the rule of how layers meet would leave the pure domain, its property tests and mutation testing.
