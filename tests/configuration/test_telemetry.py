from voice_bridge.configuration.telemetry import exports_telemetry, reports_errors


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
