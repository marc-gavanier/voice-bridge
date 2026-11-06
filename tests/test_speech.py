from pont_vocal.speech import UtteranceDetector, split_sentences

RATE = 96000
PACKET_S = 0.02
PACKET_BYTES = int(RATE * PACKET_S)


def loud():
    return (10000).to_bytes(2, "little", signed=True) * (PACKET_BYTES // 2)


def quiet():
    return bytes(PACKET_BYTES)


def detector(**kwargs):
    defaults = dict(threshold=500, silence_s=0.8, max_s=30, min_voice_s=0.2, preroll_s=0.1, barge_in_s=0.1)
    return UtteranceDetector(**{**defaults, **kwargs})


def feed(d, chunk, count, start=0.0):
    now = start
    for _ in range(count):
        now += PACKET_S
        d.feed(chunk, now)
    return now


def test_returns_nothing_while_speaking():
    d = detector()
    now = feed(d, loud(), 50)
    assert d.poll(now) is None


def test_returns_utterance_after_silence():
    d = detector()
    now = feed(d, loud(), 50)
    now = feed(d, quiet(), 45, now)
    utterance = d.poll(now)
    assert utterance is not None
    assert len(utterance) >= 50 * PACKET_BYTES


def test_returns_utterance_only_once():
    d = detector()
    now = feed(d, loud(), 50)
    now = feed(d, quiet(), 45, now)
    d.poll(now)
    assert d.poll(now) is None


def test_ignores_short_noise():
    d = detector()
    now = feed(d, loud(), 3)
    now = feed(d, quiet(), 45, now)
    assert d.poll(now) is None


def test_silence_alone_produces_nothing():
    d = detector()
    now = feed(d, quiet(), 200)
    assert d.poll(now) is None


def test_keeps_audio_just_before_voice():
    d = detector()
    now = feed(d, quiet(), 20)
    now = feed(d, loud(), 50, now)
    now = feed(d, quiet(), 45, now)
    utterance = d.poll(now)
    assert len(utterance) >= (50 + 45 + 5) * PACKET_BYTES


def test_long_speech_is_flushed_at_max_duration():
    d = detector(max_s=1)
    now = feed(d, loud(), 60)
    assert d.poll(now) is not None


def test_is_speaking_needs_sustained_voice():
    d = detector()
    now = feed(d, loud(), 2)
    assert not d.is_speaking
    feed(d, loud(), 10, now)
    assert d.is_speaking


def test_is_speaking_stops_on_silence():
    d = detector()
    now = feed(d, loud(), 20)
    feed(d, quiet(), 1, now)
    assert not d.is_speaking


def test_split_sentences_cuts_on_punctuation():
    text = "D'accord, je regarde ça maintenant. Il reste deux points à trancher ! Tu préfères lequel ?"
    assert split_sentences(text) == [
        "D'accord, je regarde ça maintenant.",
        "Il reste deux points à trancher !",
        "Tu préfères lequel ?",
    ]


def test_split_sentences_merges_very_short_ones():
    assert split_sentences("Oui. Je lance la commande tout de suite.") == [
        "Oui. Je lance la commande tout de suite."
    ]


def test_split_sentences_ignores_blank_text():
    assert split_sentences("   ") == []
