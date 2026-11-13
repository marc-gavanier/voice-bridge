from datetime import UTC, datetime, timedelta

from voice_bridge.features.conversation.domain.board import (
    Agent,
    Board,
    Finished,
    Task,
    describe,
    finish,
    start,
)
from voice_bridge.features.conversation.domain.turn_taking import AgentsChanged

MORNING = datetime(2026, 11, 13, 9, 0, tzinfo=UTC)
LATER = MORNING + timedelta(minutes=3)
SEARCHER = Agent(id="a1", kind="general-purpose", since=MORNING)
WRITER = Agent(id="a2", kind="Explore", since=MORNING)
AT_WORK = Board(at_work=(SEARCHER, WRITER))


def started_once() -> Board:
    return start(Board(), agent_id="a1", kind="general-purpose", at=MORNING)[0]


def finished_many(count: int) -> Board:
    finished = tuple(Finished(agent=SEARCHER, ended=LATER, last_message=str(index)) for index in range(count))
    return Board(at_work=(WRITER,), finished=finished)


def test_an_agent_started_is_at_work_since_it_started() -> None:
    assert started_once() == Board(at_work=(SEARCHER,))


def test_an_agent_started_has_no_description_until_its_task_tells_one() -> None:
    assert started_once().at_work[0].description == ""


def test_an_agent_started_changes_the_count_at_work() -> None:
    assert start(Board(at_work=(WRITER,)), agent_id="a1", kind="general-purpose", at=MORNING)[1] == AgentsChanged(
        at_work=2
    )


def test_an_agent_started_twice_is_counted_once() -> None:
    assert start(started_once(), agent_id="a1", kind="general-purpose", at=LATER) == (started_once(), None)


def test_an_internal_agent_without_a_type_is_not_counted() -> None:
    assert start(Board(), agent_id="a1", kind="", at=MORNING) == (Board(), None)


def test_an_agent_finished_leaves_the_others_at_work() -> None:
    assert finish(AT_WORK, agent_id="a1", last_message="Found it.", at=LATER)[0].at_work == (WRITER,)


def test_an_agent_finished_keeps_its_last_message() -> None:
    assert finish(AT_WORK, agent_id="a1", last_message="Found it.", at=LATER)[0].finished == (
        Finished(agent=SEARCHER, ended=LATER, last_message="Found it."),
    )


def test_an_agent_finished_is_counted_with_the_agents_left() -> None:
    assert finish(AT_WORK, agent_id="a2", last_message="Done.", at=LATER)[1] == AgentsChanged(at_work=1, finished=True)


def test_an_agent_never_seen_starting_changes_nothing_when_it_stops() -> None:
    assert finish(AT_WORK, agent_id="internal", last_message="Hint.", at=LATER) == (AT_WORK, None)


def test_only_the_latest_finished_agents_are_kept() -> None:
    board = finish(finished_many(20), agent_id="a2", last_message="last", at=LATER)[0]
    assert (len(board.finished), board.finished[0].last_message, board.finished[-1].last_message) == (
        20,
        "1",
        "last",
    )


def test_an_agent_at_work_takes_the_description_of_its_task() -> None:
    board = describe(AT_WORK, (Task(id="a1", description="Search the notes"),))
    assert board.at_work == (
        Agent(id="a1", kind="general-purpose", since=MORNING, description="Search the notes"),
        WRITER,
    )


def test_a_task_without_description_keeps_the_one_known() -> None:
    described = describe(AT_WORK, (Task(id="a1", description="Search the notes"),))
    assert describe(described, (Task(id="a1", description=""),)) == described


def test_the_finished_agents_keep_their_description() -> None:
    described = describe(AT_WORK, (Task(id="a1", description="Search the notes"),))
    assert finish(described, agent_id="a1", last_message="Found.", at=LATER)[0].finished[0].agent.description == (
        "Search the notes"
    )
