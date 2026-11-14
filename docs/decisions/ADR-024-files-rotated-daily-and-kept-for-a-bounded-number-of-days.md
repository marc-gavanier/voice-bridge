# ADR-024 — Events of each utterance, and files rotated daily and kept for a bounded number of days

**Date**: 2026-11-14
**Status**: accepted, partly supersedes [ADR-020](ADR-020-traces-and-metrics-kept-in-local-files-by-default.md) for the rotation of the files

## Context

Tuning the routes and the acknowledgements of [ADR-010](ADR-010-semantic-routing-chooses-the-acknowledgement-and-detects-a-stop.md), or building a corpus of what was said, needs, for each utterance, the words, the route taken, how close the other routes came and the acknowledgement actually heard. The log has some of it, on separate lines worded for people; the traces of [ADR-020](ADR-020-traces-and-metrics-kept-in-local-files-by-default.md) have none of it. Building the corpus inside the bridge would give it a feature that has nothing to do with holding a conversation.

OpenTelemetry's [log data model](https://opentelemetry.io/docs/specs/otel/logs/data-model/) defines events as log records carrying an `EventName`, and its attributes take any value, maps and arrays included. The Python SDK implements it in `opentelemetry.sdk._logs`, still under a leading underscore although the Logs API is stable in the specification, and `opentelemetry-exporter-otlp-json-file` 0.66b2, already a dependency, ships `FileLogExporter` in `opentelemetry.exporter.otlp.json.file._log_exporter`, documented in the package but not re-exported by it.

The log and the telemetry files were rotated at 5 MB with three older files kept. How far back they reached thus depended on how much was said: the bridge's log of 2026-11-10 to 2026-11-12 filled its 5 MB in under three days, about 1.7 MB a day. Keeping every utterance for a corpus asks for longer, and for a choice of how long.

## Decision

- Each utterance forwarded to Claude is one OpenTelemetry event, `voice_bridge.utterance.forwarded`: its text, whether it interrupted Claude, the end of its voice, the route taken, the three closest routes with their cosine scores, as an array of `route` and `score` maps, and the acknowledgement played after it. Each acknowledgement played is one more, `voice_bridge.acknowledgement.played`, with its sentence and the words it answers. An absent route or acknowledgement is left out, as OpenTelemetry does for any attribute without a value.
- The conversation reports them through the `Telemetry` port of [ADR-013](ADR-013-telemetry-behind-a-port-and-the-otel-extra.md), as it reports the turns; it learns the route through an `Interpreter` port, which the entry point builds from the understanding feature. Only the OpenTelemetry adapter knows the Logs API.
- Without an endpoint, the events are written to `logs.jsonl` in `telemetry_directory`, by the official `FileLogExporter` behind the SDK's `BatchLogRecordProcessor`, under the same resource as the traces and metrics. With an endpoint, they go to the global logger provider that `opentelemetry-instrument` sets up, over OTLP, and no file is written.
- The bridge holds no corpus feature: it only emits standard events, and anything built from them belongs to a tool outside it.
- The log and the three telemetry files are rotated each day at midnight, local time, by the standard library's `TimedRotatingFileHandler`; the day's file is compressed with gzip through its `namer` and `rotator`, the recipe of the [logging cookbook](https://docs.python.org/3/howto/logging-cookbook.html#using-a-rotator-and-namer-to-customize-log-rotation-processing), into a copy named after its day. `libraries/rotation/daily.py` only sets these two attributes, and the `TextIO` of ADR-020 now writes through any file handler.
- `log_retention` and `telemetry_retention` set how many days are kept, passed as the handler's `backupCount`. Both default to 30 days. Keeping every day is asked in words, `"forever"`; a number of days must be positive, so `0` is refused.

## Consequences

- Every utterance leaves one line that a tool can read without parsing the log, with `jq` or the Collector's `otlpjsonfile` receiver; the README gives a command for the words, the route and the acknowledgement of each.
- The event files hold the speaker's words. They stay on the machine, in the XDG state directory, which backups usually leave out; the README says so. With an OTLP endpoint, the words reach the collector.
- The files of a day are always whole, and a corpus can be cut by day. `zcat -f` reads the compressed days and the current file alike.
- With the defaults, the disk taken stays bounded: at 1.7 MB a day, which gzip brings to about 180 KB (the 5 MB file of 2026-11-12 compressed to 530 KB), 30 days of log take about 5 MB, and each telemetry file a comparable amount. Keeping everything is a choice made in the configuration, never a default left by neglect.
- The retention counts the days the bridge wrote, as `backupCount` counts files, not calendar days: a bridge left unused for a month still keeps its last 30 days of use. A bridge stopped at midnight rotates at its first line of the next day it runs, since the handler starts from the file's modification time.
- A day as busy as one person can speak has no size bound of its own: a whole day of speech stays in one file.
- The log exporter and the logs SDK are imported from underscored modules, which a release may move; the tests of the adapter fail if it does, and Renovate proposes each release.
- A `[logging]` section that wants the default's rotation names `voice_bridge.libraries.rotation.daily.DailyFile` with its `kept` days.

## Alternatives considered

- **The route and the acknowledgement as attributes of the turn's span**: no new signal, but a turn's spans are written only when the next words are forwarded, so the last utterance of a session killed abruptly would be lost, and the words would be spread across traces meant for timing.
- **The standard library's `logging` with OpenTelemetry's `LoggingHandler`**: the events would mix with the log, and the handler exists only under `opentelemetry-instrument`, so the default files would get none.
- **A JSON Lines file of the bridge's own format**: no dependency, but a format to define, document and read by hand, where OTLP already has one and readers.
- **A corpus built by the bridge**: refused, since it mixes a study of the speech with holding the conversation; the events let any tool build it.
- **`0` days for keeping everything**: the standard library's `backupCount=0` and Loki's `retention_period: 0` mean that, but logrotate's `rotate 0` means the opposite, keeping no old file; a word cannot be typed by mistake.
- **An unbounded default**: keeps everything without a choice, but fills the disk slowly and silently; keeping everything stays one word away.
- **Size-based rotation, kept**: the standard library's `RotatingFileHandler` bounds the disk, but how far back the files reach then depends on how much was said, and a day is split across files.
- **A handler rotating on both time and size**: the standard library has none, and a subclass that adds a size check to `TimedRotatingFileHandler` is rotation of our own; its second rotation of a day would also find the day's name taken, which the handler skips.
- **logrotate**: the standard tool on Linux, but a configuration outside the repository and the user's session, and `copytruncate` can lose lines written during the copy.
