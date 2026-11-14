import json
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Final, assert_never

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
from voice_bridge.features.conversation.domain.board import (
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
from voice_bridge.features.conversation.domain.turn_taking import AgentsChanged, ClaudeBusy, ClaudeIdle, Event

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime


logger = logging.getLogger(__name__)

AGENT_TASK: Final = "subagent"
UNRELIABLE: Final = (
    "No news from Claude Code's hooks for a message forwarded at {since}: agents may be missing from the board, "
    "or still listed at work after they finished, until Claude Code next stops and lists its tasks. "
    "The bridge's log tells whether the hooks failed."
)


def _running(tasks: tuple[TaskMessage, ...]) -> tuple[Task, ...]:
    return tuple(
        Task(id=task.id, description=task.description, kind=task.agent_type)
        for task in tasks
        if task.type == AGENT_TASK
    )


def _time(moment: datetime | None) -> str | None:
    return None if moment is None else moment.isoformat(timespec="seconds")


def _agent(agent: Agent) -> dict[str, str | int | None]:
    return {
        "id": agent.id,
        "type": agent.kind,
        "description": agent.description,
        "since": _time(agent.since),
        "resumed": agent.resumed,
        "resumed_at": _time(agent.resumed_at),
    }


def _finished(finished: Finished) -> dict[str, str | int | None]:
    return {
        **_agent(finished.agent),
        "ended": finished.ended.isoformat(timespec="seconds"),
        "last_message": finished.last_message,
    }


@dataclass(slots=True, kw_only=True)
class WorkBoard:
    clock: Callable[[], datetime]
    board: Board = field(default_factory=Board)

    def _counted(self, board: Board) -> tuple[Event, ...]:
        before = len(self.board.at_work)
        self.board = board
        return () if len(board.at_work) == before else (AgentsChanged(at_work=len(board.at_work)),)

    def _reconciled(self, tasks: tuple[TaskMessage, ...] | None, leaving: str = "") -> Board:
        if tasks is None:
            return self.board
        return reconcile(self.board, _running(tasks), at=self.clock(), leaving=leaving)[0]

    def forwarded(self) -> None:
        self.board = forwarded(self.board, at=self.clock())

    def _heard(self) -> None:
        now = self.clock()
        late = heard(self.board, at=now)
        if late.gap_since != self.board.gap_since:
            logger.warning("no news from Claude Code's hooks from %s to %s", _time(late.gap_since), _time(now))
        self.board = late

    def events_of(self, news: News, at: float) -> tuple[Event, ...]:
        match news:
            case Busy(tasks=tasks):
                self._heard()
                return (ClaudeBusy(at=at), *self._counted(self._reconciled(tasks)))
            case Idle(tasks=tasks):
                return (ClaudeIdle(), *self._counted(self._reconciled(tasks)))
            case AgentStarted(agent_id=agent_id, agent_type=kind):
                return self._counted(start(self.board, agent_id=agent_id, kind=kind, at=self.clock())[0])
            case AgentFinished(agent_id=agent_id, last_message=last_message, tasks=tasks):
                reconciled = self._reconciled(tasks, leaving=agent_id)
                return self._counted(
                    finish(reconciled, agent_id=agent_id, last_message=last_message, at=self.clock())[0]
                )
            case _:
                assert_never(news)

    def _reliability(self) -> dict[str, str | bool]:
        since = unreliable_since(self.board, now=self.clock())
        if since is None:
            return {"reliable": True}
        moment = since.isoformat(timespec="seconds")
        logger.warning("board read while unreliable since %s", moment)
        return {"reliable": False, "unreliable_since": moment, "reason": UNRELIABLE.format(since=moment)}

    def report(self) -> str:
        return json.dumps(
            {
                "now": self.clock().isoformat(timespec="seconds"),
                "at_work": [_agent(agent) for agent in self.board.at_work],
                "finished": [_finished(finished) for finished in self.board.finished],
                **self._reliability(),
            },
            ensure_ascii=False,
        )
