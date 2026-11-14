# ADR-020 — Traces and metrics kept in local files by default

**Date**: 2026-11-14
**Status**: accepted, partly supersedes [ADR-013](ADR-013-telemetry-behind-a-port-and-the-otel-extra.md) for the default adapter and the dependencies, and partly superseded by [ADR-024](ADR-024-files-rotated-daily-and-kept-for-a-bounded-number-of-days.md): the files are rotated daily and kept for a set number of days

## Context

[ADR-013](ADR-013-telemetry-behind-a-port-and-the-otel-extra.md) reported the turns through a `Telemetry` port whose default adapter did nothing: without an OTLP endpoint and a collector to receive it, no trace and no metric was kept. Analysing a run thus required running a collector beforehand, and a run nobody planned to study left only the log's timing lines, rebuilt by hand. The log, on the other hand, is always written to a rotated file under `~/.local/state/voice-bridge/log/`.

OpenTelemetry specifies a [file exporter](https://opentelemetry.io/docs/specs/otel/protocol/file-exporter/): the [OTLP JSON encoding](https://opentelemetry.io/docs/specs/otlp/#json-protobuf-encoding), one export request per line, in JSON Lines (`.jsonl`). On 2026-11-14, the OpenTelemetry Python project publishes it as [`opentelemetry-exporter-otlp-json-file`](https://pypi.org/project/opentelemetry-exporter-otlp-json-file/), from [its own repository](https://github.com/open-telemetry/opentelemetry-python/tree/main/exporter/opentelemetry-exporter-otlp-json-file), released with the SDK since 0.64b0 in June 2026; 0.66b2, of 2026-10-29, requires `opentelemetry-sdk~=1.45.2`, the version the bridge already used. Its span, metric and log exporters write to a path, opened in append mode, or to any text stream, and default to stdout. They are registered as `otlp_json_file` for `OTEL_*_EXPORTER`, but `opentelemetry-instrument` builds them without arguments, so they would write to stdout, which carries the MCP channel to Claude Code.

## Decision

- Without an OTLP endpoint and without an `OTEL_*_EXPORTER` chosen, the bridge writes its traces and metrics with the official file exporter to `traces.jsonl` and `metrics.jsonl` in `telemetry_directory`, `~/.local/state/voice-bridge/telemetry` by default, the XDG state directory next to the log. The spans go through the SDK's `BatchSpanProcessor`, the metrics through its `PeriodicExportingMetricReader`, under a resource named `voice-bridge`; the SDK flushes both when the process exits.
- The bridge builds these providers itself, in the OpenTelemetry adapter, and passes the exporters a stream, never a path left empty, so that nothing reaches stdout.
- Each file is rotated like the log, at 5 MB with three older files kept, by the standard library's `RotatingFileHandler`, behind a small `TextIO`, `libraries/rotation`, which the exporter takes as its stream. A rollover happens between two writes, and the exporter writes one whole line at a time, so a line is never split across two files.
- `opentelemetry-api`, `opentelemetry-sdk` and `opentelemetry-exporter-otlp-json-file` become dependencies of every install. The `otel` extra keeps what only the export over the network needs: zero-code instrumentation, the OTLP and Prometheus exporters, the log and system metrics instrumentations.
- With an OTLP endpoint or an exporter chosen, the bridge behaves as in ADR-013, through `opentelemetry-instrument`, and writes no file. The standard `OTEL_SDK_DISABLED=true` turns the files off, since the SDK's providers then hand out tracers and meters that record nothing.
- The core keeps its `Telemetry` port: only the adapter imports OpenTelemetry, and the entry point imports the adapter lazily, as before.

## Consequences

- Every run keeps its traces and metrics, readable with `jq`, with no container or collector to run; the README gives the command for the median of each step. The OpenTelemetry Collector's `otlpjsonfile` receiver can replay the files into any backend later.
- Every install carries the API, the SDK, the file exporter and the OTLP JSON encoding, a few pure Python packages from the OpenTelemetry project; the bridge started by any means keeps its files, and so does the rehearsal, which holds the same conversation: it writes to the same files, under the same service name, so its turns count in the medians unless it is given another `telemetry_directory`.
- The do-nothing adapter of ADR-013 has no caller left and is removed; the do-nothing stall callback stays for the recorder.
- The file exporter is still a beta (`0.66b2`), like the Prometheus exporter and the instrumentations already in the `otel` extra, and the file exporter specification is in development: a change of format would come with a release, which Renovate proposes.
- The trace of a turn still lasts until the next words are forwarded or the bridge stops, so the last turn of a session killed abruptly is lost, as in ADR-013.
- The files and their rotated copies take at most 40 MB.

## Alternatives considered

- **The `otel` extra added by the launcher every time**: the files would depend on the launcher, and a bridge or a rehearsal started otherwise would keep nothing; it would also start `opentelemetry-instrument` with exporters that write to stdout or to a collector absent by default.
- **`OTEL_TRACES_EXPORTER=otlp_json_file` through zero-code instrumentation**: the standard switch, but the exporter is then built without a path and writes to stdout, which would corrupt the MCP channel.
- **The SDK's `ConsoleSpanExporter` and `ConsoleMetricExporter` writing to a file**: in the SDK already, but their output is the SDK's own JSON, not OTLP, which no tool reads back.
- **The exporter's `path` argument**: simplest, but the file would grow without bound, unlike the log.
- **A collector run locally, writing with its `file` exporter**: the format and rotation come built in, but a process to install and keep running, which this decision means to avoid.
- **Third-party file exporters on PyPI**, such as `otel-file-exporter`: maintained outside the OpenTelemetry project, while the official package follows the SDK's releases.
