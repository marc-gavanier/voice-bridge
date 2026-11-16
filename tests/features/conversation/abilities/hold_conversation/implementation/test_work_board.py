import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest

from voice_bridge.features.conversation.abilities.hold_conversation.domain.assistant import (
    ToolCall,
    ToolCallCompleted,
    ToolCallUpdate,
    TurnEnded,
    TurnStarted,
)
from voice_bridge.features.conversation.abilities.hold_conversation.implementation.work_board import WorkBoard
from voice_bridge.features.conversation.domain.board import Task
from voice_bridge.features.conversation.domain.turn_taking import AgentsChanged, ClaudeBusy, ClaudeIdle

MORNING = datetime(2026, 11, 13, 9, 0, tzinfo=UTC)
STARTED = ToolCall(tool_call_id="a1", title="general-purpose")
SEARCH = Task(id="a1", description="Search the notes", kind="general-purpose")
DESCRIBED = TurnEnded(working=True, agents=(SEARCH,))
FINISHED = ToolCallCompleted(tool_call_id="a1", content="Found three.")


def board() -> WorkBoard:
    return WorkBoard(clock=lambda: MORNING)


def board_with_one_at_work() -> WorkBoard:
    work = board()
    _ = work.events_of(STARTED, 0.0)
    _ = work.events_of(DESCRIBED, 0.0)
    return work


def board_with_one_finished() -> WorkBoard:
    work = board_with_one_at_work()
    _ = work.events_of(FINISHED, 0.0)
    return work


def test_claude_busy_is_told_to_turn_taking() -> None:
    assert board().events_of(TurnStarted(), 2.0) == (ClaudeBusy(at=2.0),)


def test_claude_idle_is_told_to_turn_taking() -> None:
    assert board().events_of(TurnEnded(), 2.0) == (ClaudeIdle(),)


def test_an_agent_started_is_told_as_a_change_of_the_agents_at_work() -> None:
    assert board().events_of(STARTED, 2.0) == (AgentsChanged(at_work=1),)


def test_an_agent_finished_is_told_as_a_change_of_the_agents_at_work() -> None:
    assert board_with_one_at_work().events_of(FINISHED, 2.0) == (AgentsChanged(at_work=0),)


def test_an_internal_agent_changes_nothing() -> None:
    assert board().events_of(ToolCall(tool_call_id="i1", title=""), 2.0) == ()


def test_the_board_reports_the_agents_at_work_with_their_description() -> None:
    assert json.loads(board_with_one_at_work().report()) == {
        "now": "2026-11-13T09:00:00+00:00",
        "at_work": [
            {
                "id": "a1",
                "type": "general-purpose",
                "description": "Search the notes",
                "since": "2026-11-13T09:00:00+00:00",
                "resumed": 0,
                "resumed_at": None,
                "last_action": "",
                "last_action_at": None,
                "actions": 0,
            }
        ],
        "finished": [],
        "reliable": True,
    }


def test_the_board_reports_the_finished_agents_with_their_last_message() -> None:
    assert json.loads(board_with_one_finished().report())["finished"] == [
        {
            "id": "a1",
            "type": "general-purpose",
            "description": "Search the notes",
            "since": "2026-11-13T09:00:00+00:00",
            "resumed": 0,
            "resumed_at": None,
            "last_action": "",
            "last_action_at": None,
            "actions": 0,
            "ended": "2026-11-13T09:00:00+00:00",
            "last_message": "Found three.",
        }
    ]


WATCHING = ToolCallUpdate(tool_call_id="a1", title="Watch the CI", at=MORNING + timedelta(minutes=2, seconds=30.4))


def board_with_one_acting() -> WorkBoard:
    work = board_with_one_at_work()
    _ = work.events_of(WATCHING, 0.0)
    return work


def test_an_agents_action_changes_no_count() -> None:
    assert board_with_one_at_work().events_of(WATCHING, 2.0) == ()


def test_the_board_reports_the_latest_action_of_an_agent_at_work_and_when() -> None:
    assert json.loads(board_with_one_acting().report())["at_work"] == [
        {
            "id": "a1",
            "type": "general-purpose",
            "description": "Search the notes",
            "since": "2026-11-13T09:00:00+00:00",
            "resumed": 0,
            "resumed_at": None,
            "last_action": "Watch the CI",
            "last_action_at": "2026-11-13T09:02:30+00:00",
            "actions": 1,
        }
    ]


def board_finished_with_its_task() -> WorkBoard:
    work = board()
    _ = work.events_of(STARTED, 0.0)
    _ = work.events_of(ToolCallCompleted(tool_call_id="a1", agents=(Task(id="a1", description="Search"),)), 0.0)
    return work


def test_a_finished_agent_takes_the_description_told_when_it_stops() -> None:
    assert board_finished_with_its_task().board.finished[0].agent.description == "Search"


def board_with_one_resumed() -> WorkBoard:
    work = board_with_one_finished()
    _ = work.events_of(STARTED, 0.0)
    return work


def test_a_resumed_agent_is_told_as_a_change_of_the_agents_at_work() -> None:
    assert board_with_one_finished().events_of(STARTED, 2.0) == (AgentsChanged(at_work=1),)


def test_the_board_reports_how_often_an_agent_was_resumed_and_when_last() -> None:
    assert json.loads(board_with_one_resumed().report())["at_work"] == [
        {
            "id": "a1",
            "type": "general-purpose",
            "description": "Search the notes",
            "since": "2026-11-13T09:00:00+00:00",
            "resumed": 1,
            "resumed_at": "2026-11-13T09:00:00+00:00",
            "last_action": "",
            "last_action_at": None,
            "actions": 0,
        }
    ]


def test_a_stop_with_nothing_in_the_background_finishes_the_background_agents() -> None:
    assert board_with_one_at_work().events_of(TurnEnded(agents=()), 2.0) == (ClaudeIdle(), AgentsChanged(at_work=0))


def test_a_stop_without_the_task_list_leaves_the_agents_at_work() -> None:
    assert board_with_one_at_work().events_of(TurnEnded(), 2.0) == (ClaudeIdle(),)


def test_a_running_agent_missing_from_the_board_is_added_on_a_stop() -> None:
    assert board().events_of(DESCRIBED, 2.0) == (ClaudeBusy(at=2.0), AgentsChanged(at_work=1))


def test_work_left_in_the_background_without_agents_keeps_the_assistant_busy() -> None:
    assert board().events_of(TurnEnded(working=True, agents=()), 2.0) == (ClaudeBusy(at=2.0),)


def test_an_agent_stopping_while_still_listed_as_running_is_finished_once() -> None:
    work = board_with_one_at_work()
    _ = work.events_of(ToolCallCompleted(tool_call_id="a1", agents=(SEARCH,)), 2.0)
    assert (work.board.at_work, len(work.board.finished)) == ((), 1)


def test_another_agent_no_longer_running_is_finished_with_the_agent_stopping() -> None:
    work = board_with_one_at_work()
    _ = work.events_of(ToolCall(tool_call_id="a2", title="Explore"), 0.0)
    assert work.events_of(ToolCallCompleted(tool_call_id="a2", agents=()), 2.0) == (AgentsChanged(at_work=0),)


@dataclass(slots=True)
class Clock:
    now: datetime = MORNING

    def read(self) -> datetime:
        return self.now


def board_left_without_news(clock: Clock) -> WorkBoard:
    work = WorkBoard(clock=clock.read)
    work.forwarded()
    clock.now = MORNING + timedelta(minutes=1)
    return work


def test_a_message_forwarded_without_news_from_the_hooks_makes_the_board_unreliable() -> None:
    assert json.loads(board_left_without_news(Clock()).report())["reliable"] is False


def test_an_unreliable_board_tells_since_when() -> None:
    assert json.loads(board_left_without_news(Clock()).report())["unreliable_since"] == "2026-11-13T09:00:00+00:00"


def test_an_unreliable_board_tells_why() -> None:
    assert "Claude Code's hooks" in json.loads(board_left_without_news(Clock()).report())["reason"]


def test_an_unreliable_board_read_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    _ = board_left_without_news(Clock()).report()
    assert "board read while unreliable since 2026-11-13T09:00:00+00:00" in caplog.text


def test_claude_busy_in_time_after_a_message_keeps_the_board_reliable() -> None:
    clock = Clock()
    work = WorkBoard(clock=clock.read)
    work.forwarded()
    _ = work.events_of(TurnStarted(), 0.0)
    clock.now = MORNING + timedelta(minutes=1)
    assert json.loads(work.report())["reliable"] is True


def test_claude_busy_too_late_is_logged_as_a_gap(caplog: pytest.LogCaptureFixture) -> None:
    _ = board_left_without_news(Clock()).events_of(TurnStarted(), 0.0)
    assert "no news from Claude Code's hooks from 2026-11-13T09:00:00+00:00" in caplog.text


def test_a_stop_listing_the_tasks_after_a_gap_makes_the_board_reliable_again() -> None:
    work = board_left_without_news(Clock())
    _ = work.events_of(TurnStarted(), 0.0)
    _ = work.events_of(TurnEnded(agents=()), 0.0)
    assert json.loads(work.report())["reliable"] is True
