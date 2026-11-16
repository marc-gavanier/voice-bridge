from collections import Counter

from hypothesis import given
from hypothesis import strategies as st

from voice_bridge.features.speaking.domain.shuffle import next_pass

TRACKS = st.lists(st.integers(), unique=True).map(tuple)
TWO_OR_MORE = st.lists(st.integers(), unique=True, min_size=2).map(tuple)


@given(TRACKS, st.none() | st.integers())
def test_a_pass_plays_every_track_once(tracks: tuple[int, ...], last: int | None) -> None:
    assert Counter(next_pass(tracks, last=last)) == Counter(tracks)


@given(TWO_OR_MORE, st.data())
def test_a_pass_of_two_tracks_or_more_never_starts_with_the_last_one_played(
    tracks: tuple[int, ...], data: st.DataObject
) -> None:
    last = data.draw(st.sampled_from(tracks))
    assert next_pass(tracks, last=last)[0] != last
