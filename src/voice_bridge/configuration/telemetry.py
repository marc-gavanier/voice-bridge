from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Mapping

OTLP_ENDPOINTS: Final = (
    "OTEL_EXPORTER_OTLP_ENDPOINT",
    "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
    "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT",
)


EXPORTERS: Final = ("OTEL_TRACES_EXPORTER", "OTEL_METRICS_EXPORTER", "OTEL_LOGS_EXPORTER")


def exports_telemetry(environ: Mapping[str, str]) -> bool:
    return any(environ.get(name) for name in OTLP_ENDPOINTS) or any(
        environ.get(name, "none") not in {"", "none"} for name in EXPORTERS
    )


def reports_errors(environ: Mapping[str, str]) -> bool:
    return bool(environ.get("SENTRY_DSN"))
