import json
from datetime import UTC, datetime

from voice_bridge.features.conversation.abilities.hold_conversation.implementation.claude_activity import (
    AgentFinished,
    AgentStarted,
    Busy,
    Idle,
    Task,
)
from voice_bridge.features.conversation.abilities.hold_conversation.implementation.work_board import WorkBoard
from voice_bridge.features.conversation.domain.turn_taking import AgentsChanged, ClaudeBusy, ClaudeIdle

MORNING = datetime(2026, 11, 13, 9, 0, tzinfo=UTC)
STARTED = AgentStarted(agent_id="a1", agent_type="general-purpose")
DESCRIBED = Busy(tasks=(Task(id="a1", description="Search the notes"),))
FINISHED = AgentFinished(agent_id="a1", agent_type="general-purpose", last_message="Found three.")


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
    assert board().events_of(Busy(), 2.0) == (ClaudeBusy(at=2.0),)


def test_claude_idle_is_told_to_turn_taking() -> None:
    assert board().events_of(Idle(), 2.0) == (ClaudeIdle(),)


def test_an_agent_started_is_told_as_a_change_of_the_agents_at_work() -> None:
    assert board().events_of(STARTED, 2.0) == (AgentsChanged(at_work=1),)


def test_an_agent_finished_is_told_as_a_change_of_the_agents_at_work() -> None:
    assert board_with_one_at_work().events_of(FINISHED, 2.0) == (AgentsChanged(at_work=0, finished=True),)


def test_an_internal_agent_changes_nothing() -> None:
    assert board().events_of(AgentStarted(agent_id="i1"), 2.0) == ()


def test_the_board_reports_the_agents_at_work_with_their_description() -> None:
    assert json.loads(board_with_one_at_work().report()) == {
        "now": "2026-11-13T09:00:00+00:00",
        "at_work": [
            {
                "id": "a1",
                "type": "general-purpose",
                "description": "Search the notes",
                "since": "2026-11-13T09:00:00+00:00",
            }
        ],
        "finished": [],
    }


def test_the_board_reports_the_finished_agents_with_their_last_message() -> None:
    assert json.loads(board_with_one_finished().report())["finished"] == [
        {
            "id": "a1",
            "type": "general-purpose",
            "description": "Search the notes",
            "since": "2026-11-13T09:00:00+00:00",
            "ended": "2026-11-13T09:00:00+00:00",
            "last_message": "Found three.",
        }
    ]


def board_finished_with_its_task() -> WorkBoard:
    work = board()
    _ = work.events_of(STARTED, 0.0)
    _ = work.events_of(AgentFinished(agent_id="a1", tasks=(Task(id="a1", description="Search"),)), 0.0)
    return work


def test_a_finished_agent_takes_the_description_told_when_it_stops() -> None:
    assert board_finished_with_its_task().board.finished[0].agent.description == "Search"
