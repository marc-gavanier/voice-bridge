import audioop
import logging
import queue
import threading
import time

import pymumble_py3 as pymumble
from pymumble_py3.callbacks import PYMUMBLE_CLBK_SOUNDRECEIVED

from pont_vocal.speech import UtteranceDetector, is_noise, split_sentences
from pont_vocal.voice import synthesize_or_skip

log = logging.getLogger(__name__)

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
        self.paused = None
        self.speaking = None
        self.scheduled = []
        self.play_end = 0.0
        self.allowed_user = config.voice_user
        self.client = pymumble.Mumble(config.mumble_host, name, port=64738, password=config.mumble_password, reconnect=True)
        self.client.callbacks.set_callback(PYMUMBLE_CLBK_SOUNDRECEIVED, self._on_sound)
        self.client.set_receive_sound(True)

    def run(self):
        self.client.start()
        self.client.is_ready()
        log.info("pont connecté")
        while not self.voice.is_ready():
            time.sleep(2)
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

    def interrupt(self, rms=0, now=None):
        now = time.monotonic() if now is None else now
        self.client.sound_output.clear_buffer()
        unfinished = [sentence for end, sentence in self.scheduled if end > now]
        in_progress = []
        if self.speaking and self.speaking[0] == self.generation and self.speaking[1] not in unfinished:
            in_progress = [self.speaking[1]]
        waiting = []
        while not self.sentences.empty():
            generation, sentence = self.sentences.get()
            if generation == self.generation:
                waiting.append(sentence)
        stopped = unfinished + in_progress + waiting
        self.scheduled = []
        self.play_end = now
        if self.paused is not None and not stopped:
            return
        self.paused = (self.paused or []) + stopped
        self.generation += 1
        self.interrupted = True
        log.info(f"interruption (volume {rms})")

    def schedule(self, sentence, pcm, now=None):
        now = time.monotonic() if now is None else now
        self.play_end = max(now, self.play_end) + len(pcm) / 96000
        self.scheduled = [(end, done) for end, done in self.scheduled if end > now] + [(self.play_end, sentence)]
        self.client.sound_output.add_sound(pcm)

    def handle_transcript(self, text):
        paused, self.paused = self.paused, None
        if is_noise(text):
            log.info(f"bruit écarté : {text!r}")
            if paused is not None:
                self.interrupted = False
                for sentence in paused:
                    self.sentences.put((self.generation, sentence))
            return
        interrupted, self.interrupted = self.interrupted, False
        self.on_text(text, interrupted)

    @property
    def is_talking(self):
        return self.synthesizing or not self.sentences.empty() or self.client.sound_output.get_buffer_size() > 0

    def _on_sound(self, user, chunk):
        if user["name"] != self.allowed_user:
            return
        rms = audioop.rms(chunk.pcm, 2)
        with self.detector_lock:
            self.detector.feed(chunk.pcm, time.monotonic())
            speaking = self.detector.is_speaking
        if speaking and self.is_talking:
            self.interrupt(rms)

    def _transcribe_loop(self):
        while True:
            utterance, ended_at = self.utterances.get()
            pcm, _ = audioop.ratecv(utterance, 2, 1, MUMBLE_RATE, WHISPER_RATE, None)
            text = self.transcriber.transcribe(pcm)
            log.info(f"entendu en {time.monotonic() - ended_at:.2f}s : {text}")
            self.handle_transcript(text)

    def _speak_loop(self):
        while True:
            generation, sentence = self.sentences.get()
            if generation != self.generation:
                continue
            self.synthesizing = True
            self.speaking = (generation, sentence)
            start = time.monotonic()
            pcm = synthesize_or_skip(self.voice, sentence)
            if pcm is not None:
                log.info(f"voix en {time.monotonic() - start:.2f}s pour {len(pcm) / 96000:.1f}s : {sentence}")
                if generation == self.generation:
                    self.schedule(sentence, pcm)
            self.speaking = None
            self.synthesizing = False
