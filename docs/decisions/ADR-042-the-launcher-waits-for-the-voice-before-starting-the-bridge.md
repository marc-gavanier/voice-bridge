# ADR-042 — The launcher waits for the voice before starting the bridge

**Date**: 2026-11-18
**Status**: accepted

## Context

On 2026-11-18, `scripts/claude-voice.sh` found Voxtral down, started it and launched Claude Code at once. The bridge, an MCP server that Claude Code spawns over stdio, was up within seconds, heard the speaker and forwarded their words, but Voxtral needed about 114 s to load. From 19:26:28 to 19:27:27, every sentence Claude replied with was logged as `no voice for …` with `httpcore.ConnectError: All connection attempts failed`, then dropped: the speaker heard nothing, and Claude, whose `reply` tool had answered `sent`, believed it had been heard.

Three things allowed it:

- **The unit said nothing about readiness.** `scripts/voxtral.sh` creates `voice-bridge-voxtral.service` with `systemd-run`, `Type=simple` by default, so the unit was active as soon as `uv` started, long before vLLM could speak, and its default start timeout of 90 s was shorter than the load. vLLM does not send `sd_notify`; its `/health` answers 200 only after « Application startup complete ».
- **Only the greeting waited.** `greet()` polls `/health` through `wait_until_ready` before saying hello, but Claude's replies went straight to the synthesis, and a failed synthesis only logs the sentence and moves on to the next one ([ADR-029](ADR-029-the-bridge-plays-the-voice-as-the-speech-server-streams-it.md)).
- **The `reply` tool answers before the voice.** It hands the text to the conversation and answers `sent`; the synthesis happens later, so the tool cannot report a failure it has not seen yet.

## Decision

The voice session starts only once the voice is ready, and the bridge no longer drops a reply without saying so.

- **The unit is active only when Voxtral answers.** `systemd-run` gets `Type=exec`, an `ExecStartPost=` that runs `curl` against `http://127.0.0.1:8123/health` until it answers 200, with `--retry-connrefused --retry-all-errors` so that a refused connection and a 503 are retried, and `TimeoutStartSec=` of ten minutes, the same budget as curl's `--retry-max-time`. The budget and the interval are named at the top of the script. systemd 255 accepts `ExecStartPost` as a `--property` of a transient service, with the command line as its value; this was checked on throwaway units with a server that started late (the unit became active when its health answered), one that never started (the start job failed at the timeout), and a second `start` while the first one was activating (`systemctl --user start` waits for the same job). `voxtral.sh start` therefore returns once Voxtral is ready, and when the unit is already activating it waits for it instead of failing on the existing unit name.
- **The launcher waits for it.** `scripts/claude-voice.sh` says on the console that it waits for Voxtral, about two minutes, calls `voxtral.sh start` without `--no-block`, and starts Claude Code, and so the bridge, only once it returns. If Voxtral is not ready in time, the launcher stops and points to `scripts/voxtral.sh logs`. Polling `/health` is the standard available here: vLLM implements no readiness notification of systemd's, and its documented health route is what Kubernetes probes use for the same purpose.
- **The bridge keeps a short check at startup.** The rehearsal and a speech server reached at another address start the bridge without the launcher's wait, so `greet()` still waits for the health; its longest interval drops from 5 s to 0.5 s, a named constant, so that the greeting follows readiness closely. After the launcher's wait, the first check answers at once.
- **A voice lost during a session is said, once.** When a sentence cannot be voiced, the bridge plays a warning recorded at startup with the announcements, such as « Je n'ai plus de voix : le serveur de synthèse vocale ne répond pas. », and the next failures do not repeat it until a voice plays again. The rule is a scenario of turn taking.
- **Claude learns that its reply was not said.** Before handing a reply to the conversation, the `reply` tool asks the speech server's health; if it does not answer, the tool returns an error that says the reply was not said and the user heard nothing, and to send it again in a minute. `end_session` and `play` are not checked: a goodbye that cannot be voiced still ends the session, and a recording plays without the speech server.

## Consequences

- The console waits about two minutes before Claude Code starts when Voxtral is down, instead of starting at once with a bridge that cannot speak.
- A Voxtral that never becomes ready fails the unit after ten minutes and the launcher stops, instead of a session that hears and never speaks.
- Each reply costs one more local request to `/health`, a few milliseconds.
- The warning sentence is one more line in each language's TOML file, voiced and cached with the announcements; the translations other than French and English were written for this change and wait for a review by a speaker of each language.
- Known limit: the sentences already handed to the conversation when Voxtral goes down are lost, the warning and the logs say so but do not bring them back; and between the health check and the synthesis, a reply can still fail. A follow-up could keep the sentences of a failed synthesis and say them when the health answers again, which needs a readiness state shared by the conversation and the hearing, and a decision on what to do with the words heard meanwhile.

## Alternatives considered

- **A recorded announcement while the bridge waits.** The bridge would start at once, stop transcribing and forwarding until the voice is ready, and play a recording in French, « Démarrage en cours, merci de patienter. », when it hears the speaker, with a minimal delay between two plays. Marc prefers not to start the bridge at all until the voice is ready: one wait in the launcher is simpler than a second state in the conversation, and a session that cannot speak has nothing to offer.
- **Socket activation.** systemd would hold the port and start Voxtral on the first connection, but vLLM cannot take a listening socket from systemd, and the first request would still wait for the whole load.
- **`ExecStartPre=` in the bridge's unit.** The bridge is not a unit: Claude Code spawns it over stdio as an MCP server, so there is no unit to hang the wait on.
- **`Requires=`, `BindsTo=` or `PartOf=` between the bridge and Voxtral.** The same reason, and worse: tying the bridge's lifetime to Voxtral's would stop the session's MCP server whenever Voxtral restarts, and Claude Code would lose the `voice` channel for the rest of the session.
- **`--no-block` in the launcher, as before.** Claude Code would start in parallel, about two minutes sooner, but with a bridge that cannot speak, which is the incident above.
- **A `sent` answer kept for a reply the voice cannot say.** It is the behaviour that let Claude believe it had been heard.

## Risks

- **`/health` answering too early.** If a vLLM version answered 200 before it can synthesize, the unit would be active too soon and the first sentences would fail again; the warning would then say so and the `reply` tool would not catch it. Today `/health` answers only after « Application startup complete ».
- **The start timeout.** A first start downloads the model and can take longer than ten minutes on a slow link; the unit then fails, and `scripts/voxtral.sh start` must be run again once the download is cached, or the budget raised in the script.
