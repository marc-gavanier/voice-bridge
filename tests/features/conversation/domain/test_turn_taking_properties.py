from collections import Counter
from dataclasses import fields
from functools import reduce

from hypothesis import given
from hypothesis import strategies as st

from voice_bridge.features.conversation.domain.turn_taking import (
    Asked,
    AwaitHold,
    AwaitSilence,
    Command,
    Conversation,
    Event,
    Forward,
    HoldLasted,
    SilenceLasted,
    SoundDismissed,
    SpeechEnded,
    SpeechStarted,
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
    st.builds(
        Asked,
        sentences=st.lists(st.text(min_size=1), max_size=3).map(tuple),
        working=st.booleans(),
        ending=st.booleans(),
    ),
    st.builds(
        Synthesized, ticket=TICKETS, pcm=st.just(b""), duration=st.floats(min_value=0.0, max_value=5.0), at=MOMENTS
    ),
    st.builds(SynthesisFailed, ticket=TICKETS),
    st.builds(VoiceDetected, at=MOMENTS),
    st.builds(Transcribed, text=st.text(), noise=st.booleans(), stop_at=st.none() | MOMENTS),
    st.builds(SoundDismissed),
    st.builds(SpeechStarted, at=MOMENTS),
    st.builds(SpeechEnded, at=MOMENTS),
    st.builds(SilenceLasted, ticket=TICKETS, at=MOMENTS),
    st.builds(HoldLasted, ticket=TICKETS),
)
FLAGS = [field.name for field in fields(Conversation) if field.default is False]


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


def forwards(commands: tuple[Command, ...]) -> int:
    return sum(1 for command in commands if isinstance(command, Forward))


def words(events: list[Event]) -> int:
    return sum(1 for event in events if isinstance(event, Transcribed) and not event.noise)


@given(st.lists(EVENTS, max_size=50))
def test_words_are_never_forwarded_more_often_than_they_are_said(events: list[Event]) -> None:
    assert forwards(commands_of(events)) <= words(events)


@given(st.lists(EVENTS, max_size=50))
def test_a_synthesis_ticket_is_never_reused(events: list[Event]) -> None:
    assert reused_tickets(commands_of(events)) == []


def states_of(events: list[Event]) -> list[Conversation]:
    def advance(states: list[Conversation], event: Event) -> list[Conversation]:
        return [*states, step(states[-1], event)[0]]

    return reduce(advance, events, [Conversation()])


def wait_tickets(commands: tuple[Command, ...]) -> list[int]:
    return [command.ticket for command in commands if isinstance(command, AwaitSilence | AwaitHold)]


@given(st.lists(EVENTS, max_size=50))
def test_every_flag_of_the_conversation_stays_a_boolean(events: list[Event]) -> None:
    assert [
        (name, getattr(state, name))
        for state in states_of(events)
        for name in FLAGS
        if not isinstance(getattr(state, name), bool)
    ] == []


@given(st.lists(EVENTS, max_size=50))
def test_a_wait_ticket_is_never_reused(events: list[Event]) -> None:
    tickets = wait_tickets(commands_of(events))
    assert len(tickets) == len(set(tickets))
