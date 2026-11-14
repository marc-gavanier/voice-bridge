from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Mapping

    from voice_bridge.configuration.settings import Settings

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


def run_attributes(settings: Settings, *, voice: str, pace: str) -> dict[str, str | float | bool]:
    hearing = settings.hearing
    return {
        "voice_bridge.language": settings.language,
        "voice_bridge.hearing.silence": hearing.silence,
        "voice_bridge.hearing.settle": hearing.settle,
        "voice_bridge.hearing.smart_turn": hearing.smart_turn,
        "voice_bridge.hearing.turn_threshold": hearing.turn_threshold,
        "voice_bridge.whisper.model": settings.whisper.model,
        "voice_bridge.speech.model": settings.speech.model,
        "voice_bridge.speech.voice": voice,
        "voice_bridge.speech.speed": settings.speech.speed,
        "voice_bridge.speech.pace": pace,
    }
