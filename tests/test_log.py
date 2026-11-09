import io
import logging
import re

from voice_bridge.log import setup_log


def test_log_lines_start_with_date_and_time():
    stream = io.StringIO()
    setup_log(stream)
    logging.getLogger("voice_bridge.test").info("pont connecté")
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3} pont connecté\n", stream.getvalue())
