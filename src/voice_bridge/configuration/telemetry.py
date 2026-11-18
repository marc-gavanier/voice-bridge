from typing import TYPE_CHECKING, Final

from voice_bridge.configuration.settings import SmartTurnEndOfTurnSettings

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
    end_of_turn = settings.end_of_turn
    judged = (
        {"voice_bridge.hearing.turn_threshold": end_of_turn.smart_turn.turn_threshold}
        if isinstance(end_of_turn, SmartTurnEndOfTurnSettings)
        else {}
    )
    return {
        "voice_bridge.language": settings.language,
        "voice_bridge.hearing.silence": end_of_turn.silence,
        "voice_bridge.hearing.settle": end_of_turn.settle,
        "voice_bridge.hearing.smart_turn": end_of_turn.adapter == "smart_turn",
        **judged,
        "voice_bridge.whisper.model": settings.speech_recognition.faster_whisper.model,
        "voice_bridge.speech.model": settings.speech_synthesis.openai.model,
        "voice_bridge.speech.voice": voice,
        "voice_bridge.speech.speed": settings.speech_synthesis.speed,
        "voice_bridge.speech.pace": pace,
        "voice_bridge.claude.model": settings.claude.model or "default",
        "voice_bridge.claude.subagent_model": settings.claude.subagent_model or "default",
    }
