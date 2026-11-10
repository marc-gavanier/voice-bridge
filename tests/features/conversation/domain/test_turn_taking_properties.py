from collections import Counter
from functools import reduce

from hypothesis import given
from hypothesis import strategies as st

from voice_bridge.features.conversation.domain.turn_taking import (
    Asked,
    Command,
    Conversation,
    Event,
    SynthesisFailed,
    Synthesize,
    Synthesized,
    Transcribed,
    VoiceDetected,
    step,
)

TICKETS = st.integers(min_value=0, max_value=10)
MOMENTS = st.floats(min_value=0.0, max_value=100.0)
EVENTS: st.SearchStrategy[Event] = st.one_of(
    st.builds(Asked, sentences=st.lists(st.text(min_size=1), max_size=3).map(tuple)),
    st.builds(
        Synthesized, ticket=TICKETS, pcm=st.just(b""), duration=st.floats(min_value=0.0, max_value=5.0), at=MOMENTS
    ),
    st.builds(SynthesisFailed, ticket=TICKETS),
    st.builds(VoiceDetected, at=MOMENTS),
    st.builds(Transcribed, text=st.text(), noise=st.booleans()),
)


def commands_of(events: list[Event]) -> tuple[Command, ...]:
    def advance(
        history: tuple[Conversation, tuple[Command, ...]], event: Event
    ) -> tuple[Conversation, tuple[Command, ...]]:
        state, commands = step(history[0], event)
        return state, (*history[1], *commands)

    return reduce(advance, events, (Conversation(), ()))[1]


def reused_tickets(commands: tuple[Command, ...]) -> list[int]:
    tickets = Counter(command.ticket for command in commands if isinstance(command, Synthesize))
    return [ticket for ticket, count in tickets.items() if count > 1]


@given(st.lists(EVENTS, max_size=50))
def test_a_synthesis_ticket_is_never_reused(events: list[Event]) -> None:
    assert reused_tickets(commands_of(events)) == []
