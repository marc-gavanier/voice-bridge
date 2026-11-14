from dataclasses import replace
from datetime import UTC, datetime, timedelta

from voice_bridge.features.conversation.domain.board import (
    TOLERATED_SILENCE,
    Agent,
    Board,
    Finished,
    Task,
    finish,
    forwarded,
    heard,
    reconcile,
    start,
    unreliable_since,
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
    assert finish(AT_WORK, agent_id="a2", last_message="Done.", at=LATER)[1] == AgentsChanged(at_work=1)


def test_an_agent_never_seen_starting_changes_nothing_when_it_stops() -> None:
    assert finish(AT_WORK, agent_id="internal", last_message="Hint.", at=LATER) == (AT_WORK, None)


def test_only_the_latest_finished_agents_are_kept() -> None:
    board = finish(finished_many(20), agent_id="a2", last_message="last", at=LATER)[0]
    assert (len(board.finished), board.finished[0].last_message, board.finished[-1].last_message) == (
        20,
        "1",
        "last",
    )


SEARCH = Task(id="a1", description="Search the notes", kind="general-purpose")
BACKGROUND = replace(SEARCHER, description="Search the notes", background=True)
IN_BACKGROUND = Board(at_work=(BACKGROUND, WRITER))


def test_an_agent_at_work_takes_the_description_of_its_task() -> None:
    assert reconcile(AT_WORK, (SEARCH,), at=LATER, leaving="")[0].at_work == (BACKGROUND, WRITER)


def test_a_task_without_description_keeps_the_one_known() -> None:
    assert reconcile(IN_BACKGROUND, (replace(SEARCH, description=""),), at=LATER, leaving="")[0] == IN_BACKGROUND


def test_the_finished_agents_keep_their_description() -> None:
    described = reconcile(AT_WORK, (SEARCH,), at=LATER, leaving="")[0]
    assert finish(described, agent_id="a1", last_message="Found.", at=LATER)[0].finished[0].agent.description == (
        "Search the notes"
    )


def test_a_background_agent_no_longer_running_is_finished() -> None:
    assert reconcile(IN_BACKGROUND, (), at=LATER, leaving="")[0] == Board(
        at_work=(WRITER,), finished=(Finished(agent=BACKGROUND, ended=LATER, last_message=""),)
    )


def test_a_background_agent_no_longer_running_changes_the_count_at_work() -> None:
    assert reconcile(IN_BACKGROUND, (), at=LATER, leaving="")[1] == AgentsChanged(at_work=1)


def test_an_agent_never_seen_in_the_background_stays_at_work() -> None:
    assert reconcile(AT_WORK, (), at=LATER, leaving="") == (AT_WORK, None)


def test_the_agent_stopping_is_left_to_its_own_stop() -> None:
    assert reconcile(IN_BACKGROUND, (), at=LATER, leaving="a1") == (IN_BACKGROUND, None)


def test_a_running_task_missing_from_the_board_is_added_with_its_description() -> None:
    assert reconcile(Board(at_work=(WRITER,)), (SEARCH,), at=LATER, leaving="")[0] == Board(
        at_work=(WRITER, replace(BACKGROUND, since=LATER))
    )


def test_a_running_task_added_changes_the_count_at_work() -> None:
    assert reconcile(Board(at_work=(WRITER,)), (SEARCH,), at=LATER, leaving="")[1] == AgentsChanged(at_work=2)


def test_a_running_task_already_finished_is_not_added_again() -> None:
    board = Board(finished=(Finished(agent=SEARCHER, ended=LATER, last_message="Found."),))
    assert reconcile(board, (SEARCH,), at=LATER, leaving="") == (board, None)


def test_the_agent_stopping_is_not_added_when_still_listed() -> None:
    assert reconcile(Board(), (SEARCH,), at=LATER, leaving="a1") == (Board(), None)


def test_a_running_task_without_an_agent_type_is_not_added() -> None:
    assert reconcile(Board(), (replace(SEARCH, kind=""),), at=LATER, leaving="") == (Board(), None)


def test_a_task_listed_twice_is_added_once() -> None:
    assert len(reconcile(Board(), (SEARCH, SEARCH), at=LATER, leaving="")[0].at_work) == 1


RESUMED_AT = LATER + timedelta(minutes=1)


def paused_once() -> Board:
    return finish(started_once(), agent_id="a1", last_message="Paused.", at=LATER)[0]


def resumed_once() -> Board:
    return start(paused_once(), agent_id="a1", kind="general-purpose", at=RESUMED_AT)[0]


def finished_after_a_resume() -> Board:
    return finish(resumed_once(), agent_id="a1", last_message="Done.", at=RESUMED_AT + timedelta(minutes=1))[0]


def test_a_resumed_agent_is_at_work_again_since_its_first_start() -> None:
    assert resumed_once() == Board(
        at_work=(Agent(id="a1", kind="general-purpose", since=MORNING, resumed=1, resumed_at=RESUMED_AT),)
    )


def test_a_resumed_agent_changes_the_count_at_work() -> None:
    assert start(paused_once(), agent_id="a1", kind="general-purpose", at=RESUMED_AT)[1] == AgentsChanged(at_work=1)


def test_an_agent_finished_after_a_resume_has_a_single_entry() -> None:
    assert finished_after_a_resume().finished == (
        Finished(
            agent=Agent(id="a1", kind="general-purpose", since=MORNING, resumed=1, resumed_at=RESUMED_AT),
            ended=RESUMED_AT + timedelta(minutes=1),
            last_message="Done.",
        ),
    )


def test_an_agent_resumed_twice_counts_both_resumes() -> None:
    again = finish(resumed_once(), agent_id="a1", last_message="Paused.", at=RESUMED_AT)[0]
    assert start(again, agent_id="a1", kind="general-purpose", at=LATER)[0].at_work[0].resumed == 2


def test_a_resume_of_an_agent_at_work_changes_nothing() -> None:
    assert start(resumed_once(), agent_id="a1", kind="general-purpose", at=LATER) == (resumed_once(), None)


def test_a_resume_leaves_the_other_finished_agents() -> None:
    board = Board(finished=(Finished(agent=WRITER, ended=LATER, last_message="Written."),))
    paused = finish(
        start(board, agent_id="a1", kind="general-purpose", at=MORNING)[0], agent_id="a1", last_message="", at=LATER
    )[0]
    assert start(paused, agent_id="a1", kind="general-purpose", at=RESUMED_AT)[0].finished == board.finished


SILENT_TOO_LONG = MORNING + TOLERATED_SILENCE + timedelta(seconds=1)


def forwarded_twice() -> Board:
    return forwarded(forwarded(Board(), at=MORNING), at=LATER)


def test_a_board_without_news_awaited_is_reliable() -> None:
    assert unreliable_since(Board(), now=SILENT_TOO_LONG) is None


def test_a_message_forwarded_without_news_for_a_short_while_leaves_the_board_reliable() -> None:
    assert unreliable_since(forwarded(Board(), at=MORNING), now=MORNING + TOLERATED_SILENCE) is None


def test_a_message_forwarded_without_news_for_too_long_makes_the_board_unreliable() -> None:
    assert unreliable_since(forwarded(Board(), at=MORNING), now=SILENT_TOO_LONG) == MORNING


def test_the_silence_counts_from_the_first_message_left_without_news() -> None:
    assert unreliable_since(forwarded_twice(), now=SILENT_TOO_LONG) == MORNING


def test_claude_busy_in_time_keeps_the_board_reliable() -> None:
    in_time = heard(forwarded(Board(), at=MORNING), at=MORNING + TOLERATED_SILENCE)
    assert unreliable_since(in_time, now=SILENT_TOO_LONG) is None


def test_claude_busy_too_late_leaves_the_board_unreliable() -> None:
    late = heard(forwarded(Board(), at=MORNING), at=SILENT_TOO_LONG)
    assert unreliable_since(late, now=SILENT_TOO_LONG + timedelta(hours=1)) == MORNING


def test_claude_busy_without_a_message_forwarded_changes_nothing() -> None:
    assert heard(Board(), at=LATER) == Board()


def test_a_reconciliation_makes_the_board_reliable_again() -> None:
    late = heard(forwarded(Board(), at=MORNING), at=SILENT_TOO_LONG)
    assert unreliable_since(reconcile(late, (), at=SILENT_TOO_LONG, leaving="")[0], now=SILENT_TOO_LONG) is None
