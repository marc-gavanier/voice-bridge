from array import array

from voice_bridge.features.speaking.abilities.mix.domain.mixing import Layer, Mix, pull, queue, queued


def samples(*values: int) -> bytes:
    return array("h", values).tobytes()


def mix_of(*sounds: tuple[Layer, bytes]) -> Mix:
    mix = Mix()
    for layer, pcm in sounds:
        mix = queue(mix, layer, pcm)
    return mix


def frames_of(mix: Mix, size: int, count: int) -> list[bytes]:
    frames: list[bytes] = []
    for _ in range(count):
        frame, mix = pull(mix, size)
        frames.append(frame)
    return frames


def test_an_empty_mix_holds_nothing() -> None:
    assert queued(Mix()) == 0


def test_a_sound_queued_is_held_whole() -> None:
    assert queued(mix_of((Layer.VOICE, samples(1, 2, 3)))) == len(samples(1, 2, 3))


def test_a_sound_is_pulled_frame_by_frame() -> None:
    assert frames_of(mix_of((Layer.VOICE, samples(1, 2, 3, 4))), len(samples(1, 2)), 2) == [
        samples(1, 2),
        samples(3, 4),
    ]


def test_nothing_is_pulled_until_a_whole_frame_is_queued() -> None:
    assert pull(mix_of((Layer.VOICE, samples(1))), len(samples(1, 2)))[0] == b""


def test_a_frame_not_pulled_stays_queued() -> None:
    mix = mix_of((Layer.VOICE, samples(1)))
    assert pull(mix, len(samples(1, 2)))[1] == mix


def test_a_sound_added_to_its_layer_follows_it() -> None:
    mix = mix_of((Layer.VOICE, samples(1)), (Layer.VOICE, samples(2)))
    assert pull(mix, len(samples(1, 2)))[0] == samples(1, 2)


def test_a_sound_on_an_idle_layer_waits_for_the_audio_already_queued() -> None:
    mix = mix_of((Layer.MUSIC, samples(1, 2)), (Layer.VOICE, samples(3, 4)))
    assert frames_of(mix, len(samples(1, 2)), 2) == [samples(1, 2), samples(3, 4)]


def test_a_layer_drained_starts_again_after_the_others() -> None:
    mix = mix_of((Layer.VOICE, samples(1)), (Layer.MUSIC, samples(2, 3)))
    _, played = pull(mix, len(samples(1)))
    again = queue(played, Layer.VOICE, samples(4))
    assert frames_of(again, len(samples(1)), 3) == [samples(2), samples(3), samples(4)]


def test_layers_that_overlap_are_summed() -> None:
    mix = mix_of((Layer.VOICE, samples(1)), (Layer.MUSIC, samples(10, 20)), (Layer.VOICE, samples(2, 3)))
    assert frames_of(mix, len(samples(1)), 3) == [samples(1), samples(12), samples(23)]


def test_a_sum_louder_than_full_scale_is_clipped_at_its_peak() -> None:
    mix = mix_of((Layer.VOICE, samples(1)), (Layer.MUSIC, samples(32000)), (Layer.VOICE, samples(1000)))
    assert frames_of(mix, len(samples(1)), 2)[1] == samples(32767)


def test_a_sum_quieter_than_full_scale_is_clipped_at_its_trough() -> None:
    mix = mix_of((Layer.VOICE, samples(1)), (Layer.MUSIC, samples(-32000)), (Layer.VOICE, samples(-1000)))
    assert frames_of(mix, len(samples(1)), 2)[1] == samples(-32768)


def test_a_layer_queued_after_a_frame_starts_at_the_end_of_what_is_left() -> None:
    mix = mix_of((Layer.MUSIC, samples(1, 2, 3)))
    _, played = pull(mix, len(samples(1)))
    assert queued(queue(played, Layer.VOICE, samples(9))) == len(samples(2, 3, 9))


def test_a_sound_added_to_a_layer_partly_played_follows_what_is_left_of_it() -> None:
    _, played = pull(mix_of((Layer.VOICE, samples(1, 2))), len(samples(1)))
    assert frames_of(queue(played, Layer.VOICE, samples(3)), len(samples(1)), 2) == [samples(2), samples(3)]


def test_a_sound_ending_inside_a_frame_is_followed_by_the_next_within_it() -> None:
    mix = mix_of((Layer.VOICE, samples(1)), (Layer.MUSIC, samples(10, 20)))
    assert pull(mix, len(samples(1, 2)))[0] == samples(1, 10)
