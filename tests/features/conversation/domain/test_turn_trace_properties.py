from functools import reduce

from hypothesis import given
from hypothesis import strategies as st

from voice_bridge.features.conversation.domain.turn_taking import (
    Asked,
    Command,
    Event,
    Forward,
    Play,
    SoundDismissed,
    SpeechEnded,
    StopPlaying,
    SynthesisFailed,
    Synthesize,
    Synthesized,
    Transcribed,
)
from voice_bridge.features.conversation.domain.turn_trace import FinishedTurn, Report, Trace, close, observe

TICKETS = st.integers(min_value=0, max_value=5)
MOMENTS = st.floats(min_value=0.0, max_value=100.0)
ITEMS: st.SearchStrategy[Event | Command] = st.one_of(
    st.builds(Asked, sentences=st.just(("Un.",))),
    st.builds(SpeechEnded, at=MOMENTS),
    st.builds(Transcribed, text=st.just("Bonjour."), noise=st.booleans()),
    st.builds(SoundDismissed),
    st.builds(Synthesize, ticket=TICKETS, sentence=st.just("Un.")),
    st.builds(
        Synthesized, ticket=TICKETS, pcm=st.just(b""), duration=st.floats(min_value=0.0, max_value=5.0), at=MOMENTS
    ),
    st.builds(SynthesisFailed, ticket=TICKETS),
    st.builds(Play, pcm=st.just(b"")),
    st.builds(StopPlaying, heard_at=MOMENTS),
    st.builds(Forward, text=st.just("Bonjour."), interrupted=st.booleans(), acknowledging=st.booleans()),
)
MOMENTS_OBSERVED = st.lists(st.tuples(MOMENTS, ITEMS), max_size=50)

type Moment = tuple[float, Event | Command]


def reports_of(moments: list[Moment]) -> tuple[Report, ...]:
    def advance(history: tuple[Trace, tuple[Report, ...]], moment: Moment) -> tuple[Trace, tuple[Report, ...]]:
        trace, reports = observe(history[0], *moment)
        return trace, (*history[1], *reports)

    trace, reports = reduce(advance, moments, (Trace(), ()))
    return (*reports, *close(trace))


def turns(moments: list[Moment]) -> list[FinishedTurn]:
    return [report for report in reports_of(moments) if isinstance(report, FinishedTurn)]


def forwards(moments: list[Moment]) -> list[Moment]:
    return [moment for moment in moments if isinstance(moment[1], Forward)]


def steps_ending_after_their_turn(moments: list[Moment]) -> list[FinishedTurn]:
    return [turn for turn in turns(moments) if any(step.end > turn.end for step in turn.steps)]


@given(MOMENTS_OBSERVED)
def test_every_forward_makes_exactly_one_turn(moments: list[Moment]) -> None:
    assert len(turns(moments)) == len(forwards(moments))


@given(MOMENTS_OBSERVED)
def test_no_step_ends_after_its_turn(moments: list[Moment]) -> None:
    assert steps_ending_after_their_turn(moments) == []
