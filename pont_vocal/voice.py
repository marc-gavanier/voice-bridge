import audioop
import io
import json
import urllib.request
import wave

MUMBLE_RATE = 48000
MODEL = "mistralai/Voxtral-4B-TTS-2603"


class VoxtralVoice:
    def __init__(self, url, voice):
        self.url = f"{url}/v1/audio/speech"
        self.voice = voice

    def synthesize(self, text):
        payload = json.dumps({"model": MODEL, "input": text, "voice": self.voice, "response_format": "wav"}).encode()
        request = urllib.request.Request(self.url, payload, {"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=120) as response:
            return _wav_to_mumble_pcm(response.read())


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
