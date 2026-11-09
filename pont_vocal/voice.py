import audioop
import io
import logging
import json
import urllib.request
import wave

import numpy as np

log = logging.getLogger(__name__)

MUMBLE_RATE = 48000
MODEL = "mistralai/Voxtral-4B-TTS-2603"


class VoxtralVoice:
    def __init__(self, url, voice, gain=1.0):
        self.url = f"{url}/v1/audio/speech"
        self.health_url = f"{url}/health"
        self.voice = voice
        self.gain = gain

    def synthesize(self, text):
        payload = json.dumps({"model": MODEL, "input": text, "voice": self.voice, "response_format": "wav"}).encode()
        request = urllib.request.Request(self.url, payload, {"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=120) as response:
            return boost(_wav_to_mumble_pcm(response.read()), self.gain)

    def is_ready(self):
        try:
            with urllib.request.urlopen(self.health_url, timeout=2) as response:
                return response.status == 200
        except OSError:
            return False


def synthesize_or_skip(voice, sentence):
    try:
        return voice.synthesize(sentence)
    except Exception as error:
        log.info(f"voix impossible ({error}) : {sentence}")
        return None


def boost(pcm, gain):
    samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float64) / 32768
    limited = np.tanh(samples * gain)
    return (limited * 32767).astype(np.int16).tobytes()


def _wav_to_mumble_pcm(data):
    with wave.open(io.BytesIO(data)) as wav:
        rate, channels, width = wav.getframerate(), wav.getnchannels(), wav.getsampwidth()
        pcm = wav.readframes(wav.getnframes())
    if width != 2:
        pcm = audioop.lin2lin(pcm, width, 2)
    if channels == 2:
        pcm = audioop.tomono(pcm, 2, 0.5, 0.5)
    if rate != MUMBLE_RATE:
        pcm, _ = audioop.ratecv(pcm, 2, 1, rate, MUMBLE_RATE, None)
    return pcm
