from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Mapping

OTLP_ENDPOINTS: Final = (
    "OTEL_EXPORTER_OTLP_ENDPOINT",
    "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
    "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT",
)


def exports_telemetry(environ: Mapping[str, str]) -> bool:
    return any(environ.get(name) for name in OTLP_ENDPOINTS)


def reports_errors(environ: Mapping[str, str]) -> bool:
    return bool(environ.get("SENTRY_DSN"))
