import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, assert_never

from voice_bridge.features.conversation.abilities.hold_conversation.implementation.claude_activity import (
    AgentFinished,
    AgentStarted,
    Busy,
    Idle,
    News,
)
from voice_bridge.features.conversation.abilities.hold_conversation.implementation.claude_activity import (
    Task as TaskMessage,
)
from voice_bridge.features.conversation.domain.board import Agent, Board, Finished, Task, describe, finish, start
from voice_bridge.features.conversation.domain.turn_taking import AgentsChanged, ClaudeBusy, ClaudeIdle, Event

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime


def _tasks(tasks: tuple[TaskMessage, ...]) -> tuple[Task, ...]:
    return tuple(Task(id=task.id, description=task.description) for task in tasks)


def _changed(change: AgentsChanged | None) -> tuple[Event, ...]:
    return () if change is None else (change,)


def _agent(agent: Agent) -> dict[str, str]:
    return {
        "id": agent.id,
        "type": agent.kind,
        "description": agent.description,
        "since": agent.since.isoformat(timespec="seconds"),
    }


def _finished(finished: Finished) -> dict[str, str]:
    return {
        **_agent(finished.agent),
        "ended": finished.ended.isoformat(timespec="seconds"),
        "last_message": finished.last_message,
    }


@dataclass(slots=True, kw_only=True)
class WorkBoard:
    clock: Callable[[], datetime]
    board: Board = field(default_factory=Board)

    def events_of(self, news: News, at: float) -> tuple[Event, ...]:
        match news:
            case Busy(tasks=tasks):
                self.board = describe(self.board, _tasks(tasks))
                return (ClaudeBusy(at=at),)
            case Idle():
                return (ClaudeIdle(),)
            case AgentStarted(agent_id=agent_id, agent_type=kind):
                self.board, change = start(self.board, agent_id=agent_id, kind=kind, at=self.clock())
                return _changed(change)
            case AgentFinished(agent_id=agent_id, last_message=last_message, tasks=tasks):
                described = describe(self.board, _tasks(tasks))
                self.board, change = finish(described, agent_id=agent_id, last_message=last_message, at=self.clock())
                return _changed(change)
            case _:
                assert_never(news)

    def report(self) -> str:
        return json.dumps(
            {
                "now": self.clock().isoformat(timespec="seconds"),
                "at_work": [_agent(agent) for agent in self.board.at_work],
                "finished": [_finished(finished) for finished in self.board.finished],
            },
            ensure_ascii=False,
        )
