from voice_bridge.configuration.telemetry import exports_telemetry


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
