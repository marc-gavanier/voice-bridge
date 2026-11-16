from hypothesis import given
from hypothesis import strategies as st

from voice_bridge.features.hearing.abilities.listen.domain.voicing import Voicing, is_voiced

UNIT = st.floats(min_value=0.0, max_value=1.0)
VOLUMES = st.floats(min_value=0.0, max_value=32768.0)


@given(UNIT, UNIT, VOLUMES)
def test_without_a_volume_threshold_a_sound_is_voiced_when_it_reaches_the_probability(
    threshold: float, probability: float, volume: float
) -> None:
    voicing = Voicing(volume_threshold=0.0, probability=threshold)
    assert is_voiced(voicing, probability=probability, volume=volume) == (probability >= threshold)


@given(VOLUMES, VOLUMES)
def test_a_sound_certainly_voice_is_voiced_when_it_reaches_the_volume_threshold(
    threshold: float, volume: float
) -> None:
    voicing = Voicing(volume_threshold=threshold, probability=0.0)
    assert is_voiced(voicing, probability=1.0, volume=volume) == (volume >= threshold)
