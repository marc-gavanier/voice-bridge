import logging
import json
import urllib.request

from voice_bridge.libraries.audio.pcm import boost
from voice_bridge.libraries.audio.wav import decode

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
            return boost(decode(response.read(), rate=MUMBLE_RATE), self.gain)

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

