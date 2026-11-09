from types import SimpleNamespace

import pont_vocal.bridge as bridge_module
from pont_vocal.bridge import VoiceBridge


class FakeSoundOutput:
    def __init__(self):
        self.buffer = bytearray()

    def add_sound(self, pcm):
        self.buffer.extend(pcm)

    def clear_buffer(self):
        self.buffer.clear()

    def get_buffer_size(self):
        return len(self.buffer) / 96000


class FakeMumble:
    def __init__(self, *args, **kwargs):
        self.sound_output = FakeSoundOutput()
        self.callbacks = SimpleNamespace(set_callback=lambda *a: None)

    def set_receive_sound(self, value):
        pass


def make_bridge(monkeypatch):
    monkeypatch.setattr(bridge_module.pymumble, "Mumble", FakeMumble)
    config = SimpleNamespace(voice_threshold=500, voice_user="marc", mumble_host="h", mumble_password="p")
    received = []
    bridge = VoiceBridge(config, transcriber=None, voice=None, on_text=lambda text, interrupted: received.append((text, interrupted)))
    return bridge, received


def queued(bridge):
    items = []
    while not bridge.sentences.empty():
        items.append(bridge.sentences.get())
    return items


def test_noise_after_interruption_resumes_the_unspoken_sentences(monkeypatch):
    bridge, received = make_bridge(monkeypatch)
    bridge.say("Première phrase assez longue. Deuxième phrase assez longue.")
    bridge.interrupt(rms=900)
    assert queued(bridge) == []
    bridge.handle_transcript("Merci.")
    assert [sentence for _, sentence in queued(bridge)] == ["Première phrase assez longue.", "Deuxième phrase assez longue."]
    assert received == []


def test_resumed_sentences_belong_to_the_current_generation(monkeypatch):
    bridge, _ = make_bridge(monkeypatch)
    bridge.say("Première phrase assez longue.")
    bridge.interrupt(rms=900)
    bridge.handle_transcript("")
    assert [generation for generation, _ in queued(bridge)] == [bridge.generation]


def test_real_speech_after_interruption_drops_the_rest_and_is_marked(monkeypatch):
    bridge, received = make_bridge(monkeypatch)
    bridge.say("Première phrase assez longue. Deuxième phrase assez longue.")
    bridge.interrupt(rms=900)
    bridge.handle_transcript("Attends, j'ai une question.")
    assert queued(bridge) == []
    assert received == [("Attends, j'ai une question.", True)]


def test_repeated_interruptions_keep_the_first_saved_sentences(monkeypatch):
    bridge, _ = make_bridge(monkeypatch)
    bridge.say("Première phrase assez longue.")
    bridge.interrupt(rms=900)
    bridge.interrupt(rms=900)
    bridge.handle_transcript("Merci.")
    assert [sentence for _, sentence in queued(bridge)] == ["Première phrase assez longue."]


def test_interrupting_mid_playback_resumes_the_sentence_being_played(monkeypatch):
    bridge, _ = make_bridge(monkeypatch)
    bridge.schedule("Phrase en cours de lecture.", bytes(96000 * 2), now=100.0)
    bridge.interrupt(rms=900, now=101.0)
    bridge.handle_transcript("")
    assert [sentence for _, sentence in queued(bridge)] == ["Phrase en cours de lecture."]


def test_finished_sentences_are_not_resumed(monkeypatch):
    bridge, _ = make_bridge(monkeypatch)
    bridge.schedule("Phrase déjà finie.", bytes(96000), now=100.0)
    bridge.interrupt(rms=900, now=105.0)
    bridge.handle_transcript("")
    assert queued(bridge) == []


def test_transcript_without_interruption_is_passed_on(monkeypatch):
    bridge, received = make_bridge(monkeypatch)
    bridge.handle_transcript("Bonjour.")
    assert received == [("Bonjour.", False)]


def test_noise_without_interruption_is_dropped(monkeypatch):
    bridge, received = make_bridge(monkeypatch)
    bridge.handle_transcript("Merci.")
    assert received == []


def test_a_reply_queued_during_an_interruption_can_be_interrupted_too(monkeypatch):
    bridge, _ = make_bridge(monkeypatch)
    bridge.say("Première phrase assez longue.")
    bridge.interrupt(rms=900)
    bridge.say("Réponse arrivée pendant l'attente.")
    assert bridge.is_talking
    bridge.interrupt(rms=900)
    assert queued(bridge) == []
    bridge.handle_transcript("Merci.")
    assert [sentence for _, sentence in queued(bridge)] == ["Première phrase assez longue.", "Réponse arrivée pendant l'attente."]


def test_repeated_interruptions_do_not_duplicate_the_sentence_being_synthesized(monkeypatch):
    bridge, _ = make_bridge(monkeypatch)
    bridge.speaking = (bridge.generation, "Phrase en synthèse.")
    bridge.interrupt(rms=900)
    bridge.interrupt(rms=900)
    bridge.handle_transcript("")
    assert [sentence for _, sentence in queued(bridge)] == ["Phrase en synthèse."]
