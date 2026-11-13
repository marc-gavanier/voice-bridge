# ADR-013 — Telemetry behind a port and the otel extra, errors through the log

**Date**: 2026-11-13
**Status**: accepted

## Context

Every analysis of a run, such as the one in #30, rebuilt each turn by hand from the timing lines of the log. [OpenTelemetry](https://opentelemetry.io/docs/languages/python/) is the open standard for traces, metrics and logs, exported over OTLP to any backend; #39 asked for one trace per turn, latency metrics and the log, optional at install and at run.

Two ways make telemetry optional in Python:

- depend on `opentelemetry-api` always: its tracer and meter do nothing until an SDK is configured, which is the usual practice of libraries and apps;
- keep every OpenTelemetry import behind an extra, with a port in the core and an adapter that does nothing by default.

On 2026-11-13, `opentelemetry-instrumentation-logging` was tried with the bridge's `dictConfig` (#40): it wraps `dictConfig`, so its handler joins the ones the bridge sets, and a record was both exported and written to the local file. The log thus needs no code.

## Decision

- Turn taking reports what happened through a `Telemetry` port of `hold_conversation`, called with each finished turn and each counted event. A pure domain, `turn_trace`, folds the timestamped events and commands of turn taking into turns: a turn runs from the end of the speaker's voice until their next words are forwarded, with a step for each transcription, the settle, the wait for Claude's first reply, each synthesis and each playback, cut at an interruption.
- The default adapter does nothing. The OpenTelemetry adapter, the only module that imports `opentelemetry`, creates the spans after the fact with their own start and end times, and records the durations, the counts and the audio stalls the Mumble library reports.
- The adapter is loaded only when the `otel` extra is installed and an `OTEL_EXPORTER_OTLP_*ENDPOINT` variable is set. The providers and exporters come from zero-code instrumentation, `opentelemetry-instrument`, which also exports the log, rather than from code in the bridge.
- The collector is each user's choice: the bridge names none. One collector can route each signal to its own tool.
- An error nobody expected is logged with its traceback before the entry point exits, instead of reaching only stderr, which Claude Code reads and the log never kept.
- Errors reach Sentry through its own SDK, in a `sentry` extra, initialized only when `SENTRY_DSN` is set: its logging integration turns each record at `ERROR` or above into an event. Breadcrumbs and the local variables of frames are turned off, since both would carry what the speaker said and Claude's replies.

## Consequences

- Without the extra or without an endpoint, the bridge runs as before and imports nothing of OpenTelemetry; the core names no vendor, in line with [ADR-005](ADR-005-features-and-abilities-on-a-hexagonal-core.md) and the study of #33.
- The only module loaded lazily, `entrypoints/telemetry.py`, carries a per-file exception to Ruff's `PLC0415` in `pyproject.toml`.
- A turn is reported when the next words are forwarded, or when the conversation ends, so the trace of the last turn of a session killed abruptly is lost.
- The OpenTelemetry SDK is a development dependency, so the adapter is tested with in-memory exporters.

## Alternatives considered

- **`opentelemetry-api` always**: less code and the common practice, but a dependency of every install and a vendor's name in the core, for a feature most runs leave off.
- **Spans opened and closed live in each ability**: would spread the instrumentation over hearing, conversation and speaking, which may not import each other; the events turn taking already sees carry every timestamp needed.
- **Errors to Sentry over OTLP**: Sentry accepts OTLP, but whether an exported log record becomes an issue, grouped and alerted on like the SDK's events, was not checked.
- **Configuring the SDK in the bridge**: duplicates what `opentelemetry-instrument` reads from the standard `OTEL_*` variables.
