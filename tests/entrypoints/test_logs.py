import logging

import pytest

from voice_bridge.entrypoints.logs import run_logged


async def failing(message: str) -> None:
    raise ValueError(message)


async def succeeding(message: str) -> None:
    logging.getLogger("voice_bridge.test").info(message)


def logged(caplog: pytest.LogCaptureFixture) -> list[tuple[str, bool]]:
    return [(record.getMessage(), record.exc_info is not None) for record in caplog.records]


def test_an_unexpected_error_still_stops_the_run() -> None:
    with pytest.raises(ValueError, match="broken"):
        run_logged(failing, "broken")


def test_an_unexpected_error_is_logged_with_its_traceback(caplog: pytest.LogCaptureFixture) -> None:
    with pytest.raises(ValueError, match="broken"):
        run_logged(failing, "broken")
    assert logged(caplog) == [("stopped on an unexpected error", True)]


def test_a_run_without_error_logs_nothing_more(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)
    run_logged(succeeding, "fine")
    assert logged(caplog) == [("fine", False)]
