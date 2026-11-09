import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import numpy as np

from pont_vocal.voice import VoxtralVoice, boost, synthesize_or_skip


def pcm(values):
    return np.array(values, dtype=np.int16).tobytes()


def samples(data):
    return np.frombuffer(data, dtype=np.int16)


def test_boost_raises_quiet_samples():
    result = samples(boost(pcm([1000, -1000]), gain=2.5))
    assert 2300 < result[0] < 2500
    assert -2500 < result[1] < -2300


def test_boost_never_clips_loud_samples():
    result = samples(boost(pcm([32767, -32768, 30000]), gain=2.5))
    assert result.max() <= 32767
    assert result.min() >= -32768
    assert result[0] > result[2] > 0


def test_boost_with_gain_one_keeps_samples_close():
    result = samples(boost(pcm([1000]), gain=1))
    assert 990 < result[0] <= 1000


def test_boost_keeps_silence():
    assert samples(boost(pcm([0, 0]), gain=2.5)).tolist() == [0, 0]


class FailingVoice:
    def synthesize(self, text):
        raise ConnectionRefusedError("Voxtral pas prêt")


class WorkingVoice:
    def synthesize(self, text):
        return b"\x01\x00"


def test_synthesize_or_skip_returns_audio_when_voice_works():
    assert synthesize_or_skip(WorkingVoice(), "Bonjour.") == b"\x01\x00"


def test_synthesize_or_skip_skips_when_voice_fails():
    assert synthesize_or_skip(FailingVoice(), "Je t'écoute.") is None


def test_synthesize_or_skip_logs_the_lost_sentence(caplog):
    synthesize_or_skip(FailingVoice(), "Je t'écoute.")
    assert "Je t'écoute." in caplog.text


def test_is_ready_is_false_when_nothing_listens():
    assert VoxtralVoice("http://127.0.0.1:9", "fr_female").is_ready() is False


def test_is_ready_is_true_when_health_answers():
    class Health(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200 if self.path == "/health" else 404)
            self.end_headers()

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Health)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        assert VoxtralVoice(f"http://127.0.0.1:{server.server_port}", "fr_female").is_ready() is True
    finally:
        server.shutdown()
