# ADR-034 — Every brick of the voice chain is swappable behind a port

**Date**: 2026-11-16
**Status**: accepted

## Context

#33 asked what replacing each brick of the chain would cost: another transport than Mumble, another assistant than Claude Code, another speech engine, another recognizer. [ADR-005](ADR-005-features-and-abilities-on-a-hexagonal-core.md) gives each ability its ports, but the study written in #33 found that half the chain is wired directly:

- **Transport.** Mumble is a library, not an adapter: the voice entry point imports eight of its names and builds pymumble's buffer itself, its `Packet` reaches the `listen` and `record` abilities, `pump_audio` decodes, chooses the speaker by certificate, logs presence and detects stalls at once, the stalls reach telemetry through a callable beside its port, and `MUMBLE_RATE` is the rate of every step. Only the sending side has a port, `Speaker`.
- **Assistant.** The conversation sees a `Claude` port. Below it, the channel relies on Claude Code's experimental `claude/channel` capability, its activity comes from Claude Code's hooks, the stop rule in *understanding* imports their format, leaving sends `SIGTERM` to Claude Code's process, and Claude Code spawns the bridge. The rehearsal already swaps the assistant for an echo, which shows where the seam is.
- **Listening.** faster-whisper is built in the entry point, behind a protocol shaped like its own call and kept in an `implementation`. It is also a hidden dependency of three other steps: the Silero model file comes from its package, Smart Turn's features use its `FeatureExtractor`, and audio files are decoded with its `decode_audio`. Replacing Whisper would break voice detection, end of turn and clip decoding. Silero's state lives in the `listen` shell.
- **Speech synthesis.** The conversation sees `Voice`, but the `speak` shell takes the concrete OpenAI-compatible client, and the clip cache builds its key from that client's fields. Any server with the OpenAI speech API already works by changing its address.
- **Acknowledgement routing.** `Scores` is a port, but MiniLM's repository and revision are constants, so changing the model is a code change.
- **Already behind a port**: end of turn (`Judge`), the pace of the speech (`Pacing`), hold music (`HoldMusic`) and telemetry (`Telemetry`).
- **Settings.** `config.toml` mixes sections named after a tool, `mumble` and `whisper`, with sections named after a function, `speech` and `hearing`. The entry point hard-wires each implementation; only Smart Turn's boolean and telemetry's environment variables choose one.

The study set Discord aside: Discord does not support voice receive for bots, and since its end-to-end encryption, DAVE, no Python library would decrypt it. That second point is wrong. Checked on 2026-11-16:

- [DAVE](https://daveprotocol.com/) is built on MLS: a bot that implements DAVE is a member of the MLS group and receives the keys like any participant ([voice connections](https://docs.discord.com/developers/topics/voice-connections)).
- [@discordjs/voice 0.19](https://github.com/discordjs/discord.js/blob/main/packages/voice/CHANGELOG.md) decrypts DAVE per user on receive.
- In Python, discord.py 2.7 supports DAVE through the `davey` package, but receiving with `discord-ext-voice-recv` needs an unmerged [pull request #54](https://github.com/imayhaveborkedit/discord-ext-voice-recv/pull/54), whose testers report corrupted streams and errors after a reconnection.
- Discord has never documented voice receive for bots, so it may break without notice; and it needs a real bot account, since automating a user account is forbidden.

For the assistant, the [Agent Client Protocol](https://agentclientprotocol.com/protocol/overview) (ACP) is the closest thing to a standard: JSON-RPC 2.0 between a client and a coding agent, with `session/new`, `session/prompt` answered with a stop reason, `session/cancel`, `session/update` notifications for message chunks, tool calls and plans, and `session/request_permission`. It is young, its support by assistants is uneven, and whether it can carry what the bridge needs, pushed messages and an interruption, is unchecked. No standard yet lets one bridge drive every assistant.

## Decision

Every brick of the chain is reached through a port in an ability's `domain`, with one adapter per tool in that ability's `implementation`, chosen by the settings and built by the entry points, as [ADR-005](ADR-005-features-and-abilities-on-a-hexagonal-core.md) already asks.

- **Transport, first.** One port for audio in and out at a rate the transport declares, the chosen speaker's frames as a neutral type, and the transport's events: speaker joined or left, stalled, disconnected, reconnected. Identity, codec and reconnection stay inside each adapter. Mumble moves from `libraries` behind this port and becomes its first adapter, with no change in behaviour; `Packet` leaves `listen` and `record`, and `MUMBLE_RATE` leaves the wiring. LiveKit and Discord are the two candidate adapters. Discord through Python waits for receive with DAVE to be merged and to hold across reconnections.
- **Assistant, second.** A neutral port of our own, whose shape follows ACP: the same notions and the same messages, a session, a prompt, its interruption, the updates that stream replies and activity, the end of a turn and of the session. One adapter per assistant, Claude Code first, holding its channel, its hooks, its tool names and its process. When ACP is a stable standard, an ACP adapter maps almost one to one. The `Claude` port is renamed, and the hook format leaves *understanding*.
- **Listening pipeline, third.** Listening is a pipeline of four steps, each with its own port and adapters: audio decoding, voice activity detection, end of turn and speech recognition. One tool may serve several steps by default, as faster-whisper does today, but each step must be swappable alone. The first change cuts the hidden dependencies: Silero from its own source, Smart Turn's features without faster-whisper, audio files decoded with PyAV directly. Then voice detection gets a port that takes Silero's state out of the shell, and speech recognition a port in `transcribe/domain` with a neutral transcript and a neutral language code.
- **Acknowledgement routing, fourth.** No new port: the embedding model's repository and revision become settings, before #56 tries a trained model.
- **Settings by port, fifth.** The settings are organised by step, that is by port: each step's section names its chosen adapter, and the adapter's own settings sit in a sub-section named after it, such as `[transport]` with `adapter = "mumble"` and `[transport.mumble]`. What belongs to the step whatever the adapter, such as the hearing thresholds, stays in the step's section. Smart Turn's boolean becomes the end of turn's adapter, and telemetry's adapter is chosen the same way while the OpenTelemetry adapter keeps reading the standard `OTEL_*` variables. The current `config.toml` breaks once; the README documents the migration, section by section, in the same pull request.
- **Speech synthesis, last.** A port in `speak/domain`, with the OpenAI-compatible client as its first adapter. Its value is for engines embedded in the bridge, online services with another API, and a proper key for the clip cache, taken from the adapter rather than from the client's fields.
- **Unchanged**: end of turn, the pace of the speech, hold music and telemetry already sit behind a port.

The work follows this order, one issue per unit: transport, assistant, the listening pipeline with its hidden dependencies first, the routing model, the settings, speech synthesis.

## Consequences

- Each adapter can be tested with fakes of its port, and `libraries/mumble/connection.py` stays the only network code omitted from coverage until a transport adapter gives it a testable seam.
- The transport port changes the README's Mermaid diagrams ([ADR-007](ADR-007-hand-written-mermaid-for-the-system.md)) and the recorder, which becomes a client of the port rather than of Mumble.
- The assistant port inverts nothing yet: Claude Code still spawns the bridge. An ACP adapter would make the bridge the client that spawns the assistant, which the port's shape allows but this decision does not do.
- The voice instructions and tool descriptions in the language files still speak to Claude Code; another assistant needs its own.
- A Discord adapter in Python rests on an unmerged pull request and on an undocumented behaviour of Discord; it is tried, not relied on, until both hold.
- Each of the six units changes wiring and settings, so the entry point and `config.toml` change several times before the settings are reorganised; the settings break only once, in their own unit.

## Alternatives considered

- **Discord ruled out**, as the study concluded. Its premise, that no library decrypts DAVE on receive, is false: a DAVE bot is a member of the MLS group, and @discordjs/voice already decrypts.
- **ACP as the assistant port itself.** It would tie the core to a protocol that is not yet stable and that Claude Code does not speak natively; a port shaped like it keeps that door open without the dependency.
- **One speech recognition port that keeps faster-whisper's bundled helpers.** It would leave voice detection, end of turn and clip decoding unable to change without Whisper.
- **A port for the embedding model.** `Scores` is already the seam; a setting is enough for another encoder, and a trained classifier from #56 would replace the router behind `Scores`.
- **A port for speech synthesis first.** The OpenAI-compatible client already covers most local servers by changing an address, so it waits until the rest is done.
- **One flat section per tool**, as today. It hides which step a tool fills and cannot say that two tools are alternatives for the same step.
- **A key per brick at the top level**, such as `transport = "mumble"` beside a `[mumble]` section, as the study suggested. It separates the choice from the step it belongs to.
