from functools import reduce
from itertools import accumulate

from hypothesis import given
from hypothesis import strategies as st

from voice_bridge.features.hearing.domain.utterance import Frame, Kept, Listening, UtteranceRules, close, hear

RULES = UtteranceRules()
GAPS = st.lists(st.floats(min_value=0.0, max_value=2.0), max_size=200)


def silent_frames(gaps: list[float]) -> list[Frame]:
    return [Frame(pcm=bytes(1920), voiced=False, at=at, duration=0.02) for at in accumulate(gaps)]


def kept_utterances(frames: list[Frame]) -> list[Kept]:
    def step(result: tuple[Listening, list[Kept]], frame: Frame) -> tuple[Listening, list[Kept]]:
        state, closing = close(hear(result[0], frame, RULES), frame.at, RULES)
        return state, [*result[1], closing] if isinstance(closing, Kept) else result[1]

    return reduce(step, frames, (Listening(), []))[1]


@given(GAPS)
def test_silence_never_makes_an_utterance_whatever_its_rhythm(gaps: list[float]) -> None:
    assert kept_utterances(silent_frames(gaps)) == []
