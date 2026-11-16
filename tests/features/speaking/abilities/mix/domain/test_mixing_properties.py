from array import array

from hypothesis import given
from hypothesis import strategies as st

from voice_bridge.features.speaking.abilities.mix.domain.mixing import Layer, Mix, pull, queue, queued

SOUND = st.lists(st.integers(min_value=-32768, max_value=32767), max_size=12).map(
    lambda values: array("h", values).tobytes()
)
FRAME = st.integers(min_value=1, max_value=6).map(lambda samples: samples * 2)
LAYER = st.sampled_from(Layer)


def mix_of(sounds: list[tuple[Layer, bytes]]) -> Mix:
    mix = Mix()
    for layer, pcm in sounds:
        mix = queue(mix, layer, pcm)
    return mix


def drained(mix: Mix, size: int) -> bytes:
    pulled, frame = b"", b"-"
    while frame:
        frame, mix = pull(mix, size)
        pulled += frame
    return pulled


@given(st.lists(SOUND), FRAME)
def test_one_layer_plays_its_sounds_unchanged_one_after_the_other(sounds: list[bytes], size: int) -> None:
    whole = b"".join(sounds)
    assert drained(mix_of([(Layer.VOICE, pcm) for pcm in sounds]), size) == whole[: len(whole) - len(whole) % size]


@given(st.lists(st.tuples(LAYER, SOUND)), FRAME)
def test_every_whole_frame_queued_is_pulled(sounds: list[tuple[Layer, bytes]], size: int) -> None:
    mix = mix_of(sounds)
    assert len(drained(mix, size)) == queued(mix) - queued(mix) % size


@given(st.lists(st.tuples(LAYER, SOUND)), FRAME)
def test_a_frame_pulled_leaves_one_frame_less_queued(sounds: list[tuple[Layer, bytes]], size: int) -> None:
    mix = mix_of(sounds)
    frame, rest = pull(mix, size)
    assert queued(rest) == queued(mix) - len(frame)
