import audioop
import re
from collections import deque

BYTES_PER_S = 96000
MIN_SENTENCE_CHARS = 12


class UtteranceDetector:
    def __init__(self, threshold, silence_s=0.8, max_s=30, min_voice_s=0.3, preroll_s=0.3, barge_in_s=0.2):
        self.threshold = threshold
        self.silence_s = silence_s
        self.max_bytes = int(max_s * BYTES_PER_S)
        self.min_voice_bytes = int(min_voice_s * BYTES_PER_S)
        self.preroll_bytes = int(preroll_s * BYTES_PER_S)
        self.barge_in_bytes = int(barge_in_s * BYTES_PER_S)
        self.buffer = bytearray()
        self.preroll = deque()
        self.preroll_size = 0
        self.voice_bytes = 0
        self.run_bytes = 0
        self.last_voice = None

    @property
    def is_speaking(self):
        return self.run_bytes >= self.barge_in_bytes

    def feed(self, pcm, now):
        if audioop.rms(pcm, 2) >= self.threshold:
            self._on_voice(pcm, now)
        else:
            self._on_silence(pcm)

    def poll(self, now):
        if not self.buffer:
            return None
        silent = self.last_voice is not None and now - self.last_voice > self.silence_s
        if silent or len(self.buffer) >= self.max_bytes:
            return self._flush()
        return None

    def _on_voice(self, pcm, now):
        if not self.buffer:
            self._take_preroll()
        self.buffer.extend(pcm)
        self.voice_bytes += len(pcm)
        self.run_bytes += len(pcm)
        self.last_voice = now

    def _on_silence(self, pcm):
        self.run_bytes = 0
        if self.buffer:
            self.buffer.extend(pcm)
            return
        self.preroll.append(pcm)
        self.preroll_size += len(pcm)
        while self.preroll_size - len(self.preroll[0]) >= self.preroll_bytes:
            self.preroll_size -= len(self.preroll.popleft())

    def _take_preroll(self):
        for chunk in self.preroll:
            self.buffer.extend(chunk)
        self.preroll.clear()
        self.preroll_size = 0

    def _flush(self):
        utterance = bytes(self.buffer) if self.voice_bytes >= self.min_voice_bytes else None
        self.buffer.clear()
        self.voice_bytes = 0
        self.last_voice = None
        return utterance


def split_sentences(text):
    sentences = []
    for part in re.split(r"(?<=[.!?…])\s+", text.strip()):
        if not part:
            continue
        if sentences and len(sentences[-1]) < MIN_SENTENCE_CHARS:
            sentences[-1] = f"{sentences[-1]} {part}"
        else:
            sentences.append(part)
    return sentences
