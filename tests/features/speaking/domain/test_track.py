from voice_bridge.features.speaking.domain.track import Track, next_chunk

TRACK = Track(pcm=b"abcdef")


def test_a_chunk_is_taken_from_the_start() -> None:
    assert next_chunk(TRACK, 4)[0] == b"abcd"


def test_the_next_chunk_follows_the_previous_one() -> None:
    _, played = next_chunk(TRACK, 2)
    assert next_chunk(played, 2)[0] == b"cd"


def test_the_track_starts_over_at_its_end() -> None:
    _, played = next_chunk(TRACK, 4)
    assert next_chunk(played, 4)[0] == b"efab"


def test_a_chunk_longer_than_the_track_loops_over_it() -> None:
    assert next_chunk(TRACK, 14)[0] == b"abcdefabcdefab"


def test_an_empty_track_gives_nothing() -> None:
    assert next_chunk(Track(pcm=b""), 4) == (b"", Track(pcm=b""))
