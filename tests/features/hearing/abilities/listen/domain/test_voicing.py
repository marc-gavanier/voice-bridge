from voice_bridge.features.hearing.abilities.listen.domain.voicing import Voicing, is_voiced

VOICING = Voicing(volume_threshold=100.0, probability=0.5)


def test_a_loud_enough_sound_scored_as_voice_is_voiced() -> None:
    assert is_voiced(VOICING, probability=0.9, volume=500.0)


def test_a_sound_scored_exactly_at_the_probability_is_voiced() -> None:
    assert is_voiced(VOICING, probability=0.5, volume=500.0)


def test_a_sound_exactly_as_loud_as_the_volume_threshold_is_voiced() -> None:
    assert is_voiced(VOICING, probability=0.9, volume=100.0)


def test_a_sound_scored_below_the_probability_is_not_voiced() -> None:
    assert not is_voiced(VOICING, probability=0.49, volume=500.0)


def test_a_sound_quieter_than_the_volume_threshold_is_not_voiced() -> None:
    assert not is_voiced(VOICING, probability=0.9, volume=99.0)
