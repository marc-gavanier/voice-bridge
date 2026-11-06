import audioop
import queue
import threading
import time

import pymumble_py3 as pymumble
from pymumble_py3.callbacks import PYMUMBLE_CLBK_SOUNDRECEIVED

from pont_vocal.speech import UtteranceDetector, split_sentences

WHISPER_RATE = 16000
MUMBLE_RATE = 48000


class VoiceBridge:
    def __init__(self, config, transcriber, voice, on_text, name="claude"):
        self.transcriber = transcriber
        self.voice = voice
        self.on_text = on_text
        self.detector = UtteranceDetector(config.voice_threshold)
        self.detector_lock = threading.Lock()
        self.utterances = queue.Queue()
        self.sentences = queue.Queue()
        self.generation = 0
        self.synthesizing = False
        self.interrupted = False
        self.allowed_user = config.voice_user
        self.client = pymumble.Mumble(config.mumble_host, name, port=64738, password=config.mumble_password, reconnect=True)
        self.client.callbacks.set_callback(PYMUMBLE_CLBK_SOUNDRECEIVED, self._on_sound)
        self.client.set_receive_sound(True)

    def run(self):
        self.client.start()
        self.client.is_ready()
        print("pont connecté", flush=True)
        self.say("Je t'écoute.")
        threading.Thread(target=self._transcribe_loop, daemon=True).start()
        threading.Thread(target=self._speak_loop, daemon=True).start()
        while True:
            time.sleep(0.05)
            with self.detector_lock:
                utterance = self.detector.poll(time.monotonic())
            if utterance:
                self.utterances.put((utterance, time.monotonic()))

    def say(self, text):
        for sentence in split_sentences(text):
            self.sentences.put((self.generation, sentence))

    def interrupt(self):
        self.generation += 1
        self.interrupted = True
        self.client.sound_output.clear_buffer()
        print("interruption", flush=True)

    @property
    def is_talking(self):
        return self.synthesizing or not self.sentences.empty() or self.client.sound_output.get_buffer_size() > 0

    def _on_sound(self, user, chunk):
        if user["name"] != self.allowed_user:
            return
        with self.detector_lock:
            self.detector.feed(chunk.pcm, time.monotonic())
            speaking = self.detector.is_speaking
        if speaking and self.is_talking:
            self.interrupt()

    def _transcribe_loop(self):
        while True:
            utterance, ended_at = self.utterances.get()
            pcm, _ = audioop.ratecv(utterance, 2, 1, MUMBLE_RATE, WHISPER_RATE, None)
            text = self.transcriber.transcribe(pcm)
            print(f"entendu en {time.monotonic() - ended_at:.2f}s : {text}", flush=True)
            if text:
                interrupted, self.interrupted = self.interrupted, False
                self.on_text(text, interrupted)

    def _speak_loop(self):
        while True:
            generation, sentence = self.sentences.get()
            if generation != self.generation:
                continue
            self.synthesizing = True
            start = time.monotonic()
            try:
                pcm = self.voice.synthesize(sentence)
            finally:
                self.synthesizing = False
            print(f"voix en {time.monotonic() - start:.2f}s pour {len(pcm) / 96000:.1f}s : {sentence}", flush=True)
            if generation == self.generation:
                self.client.sound_output.add_sound(pcm)
