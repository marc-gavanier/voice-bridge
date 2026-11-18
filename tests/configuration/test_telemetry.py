from voice_bridge.configuration.settings import Settings
from voice_bridge.configuration.telemetry import exports_telemetry, reports_errors, run_attributes


def test_no_endpoint_exports_nothing() -> None:
    assert not exports_telemetry({})


def test_an_empty_endpoint_exports_nothing() -> None:
    assert not exports_telemetry({"OTEL_EXPORTER_OTLP_ENDPOINT": ""})


def test_the_common_endpoint_exports() -> None:
    assert exports_telemetry({"OTEL_EXPORTER_OTLP_ENDPOINT": "http://127.0.0.1:4317"})


def test_an_endpoint_for_traces_only_exports() -> None:
    assert exports_telemetry({"OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": "http://127.0.0.1:4318/v1/traces"})


def test_an_endpoint_for_metrics_only_exports() -> None:
    assert exports_telemetry({"OTEL_EXPORTER_OTLP_METRICS_ENDPOINT": "http://127.0.0.1:4318/v1/metrics"})


def test_a_chosen_metrics_exporter_exports_without_an_endpoint() -> None:
    assert exports_telemetry({"OTEL_METRICS_EXPORTER": "prometheus"})


def test_a_chosen_traces_exporter_exports_without_an_endpoint() -> None:
    assert exports_telemetry({"OTEL_TRACES_EXPORTER": "console"})


def test_exporters_all_set_to_none_export_nothing() -> None:
    assert not exports_telemetry(
        {"OTEL_TRACES_EXPORTER": "none", "OTEL_METRICS_EXPORTER": "none", "OTEL_LOGS_EXPORTER": "none"}
    )


def test_an_empty_exporter_exports_nothing() -> None:
    assert not exports_telemetry({"OTEL_METRICS_EXPORTER": ""})


def test_no_sentry_dsn_reports_no_error() -> None:
    assert not reports_errors({})


def test_an_empty_sentry_dsn_reports_no_error() -> None:
    assert not reports_errors({"SENTRY_DSN": ""})


def test_a_sentry_dsn_reports_errors() -> None:
    assert reports_errors({"SENTRY_DSN": "https://key@sentry.example.org/1"})


def settings(claude: dict[str, str]) -> Settings:
    return Settings.model_validate(
        {
            "claude": claude,
            "language": "fr",
            "transport": {
                "mumble": {
                    "host": "voice.example.org",
                    "password": "secret",
                    "server_certificate": "/etc/voice-bridge/server.pem",
                    "speaker_certificate_hash": "6f0b58787b96ff978ba512c74a1c3ca4aabab441",
                }
            },
            "speech_recognition": {"faster_whisper": {"model": "large-v3"}},
            "hearing": {"settle": 1.5, "silence": 0.7, "smart_turn": True, "turn_threshold": 0.6},
            "speech": {"model": "mistralai/Voxtral-4B-TTS-2603", "speed": 1.2},
        }
    )


def test_the_run_is_described_by_the_settings_that_shape_a_turn() -> None:
    claude = {"model": "sonnet", "subagent_model": "claude-opus-5-5"}
    assert run_attributes(settings(claude), voice="fr_female", pace="atempo") == {
        "voice_bridge.language": "fr",
        "voice_bridge.hearing.silence": 0.7,
        "voice_bridge.hearing.settle": 1.5,
        "voice_bridge.hearing.smart_turn": True,
        "voice_bridge.hearing.turn_threshold": 0.6,
        "voice_bridge.whisper.model": "large-v3",
        "voice_bridge.speech.model": "mistralai/Voxtral-4B-TTS-2603",
        "voice_bridge.speech.voice": "fr_female",
        "voice_bridge.speech.speed": 1.2,
        "voice_bridge.speech.pace": "atempo",
        "voice_bridge.claude.model": "sonnet",
        "voice_bridge.claude.subagent_model": "claude-opus-5-5",
    }


def test_a_run_on_claude_codes_own_models_names_them_default() -> None:
    attributes = run_attributes(settings({}), voice="fr_female", pace="atempo")
    assert (attributes["voice_bridge.claude.model"], attributes["voice_bridge.claude.subagent_model"]) == (
        "default",
        "default",
    )
