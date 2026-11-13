from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Final

from voice_bridge.features.conversation.domain.turn_taking import AgentsChanged

if TYPE_CHECKING:
    from datetime import datetime

KEPT_FINISHED: Final = 20


@dataclass(frozen=True, slots=True, kw_only=True)
class Agent:
    id: str
    kind: str
    since: datetime
    description: str = ""


@dataclass(frozen=True, slots=True, kw_only=True)
class Finished:
    agent: Agent
    ended: datetime
    last_message: str


@dataclass(frozen=True, slots=True, kw_only=True)
class Task:
    id: str
    description: str


@dataclass(frozen=True, slots=True, kw_only=True)
class Board:
    at_work: tuple[Agent, ...] = ()
    finished: tuple[Finished, ...] = ()


type Changed = tuple[Board, AgentsChanged | None]


def start(board: Board, *, agent_id: str, kind: str, at: datetime) -> Changed:
    if not kind or any(agent.id == agent_id for agent in board.at_work):
        return board, None
    started = replace(board, at_work=(*board.at_work, Agent(id=agent_id, kind=kind, since=at)))
    return started, AgentsChanged(at_work=len(started.at_work))


def finish(board: Board, *, agent_id: str, last_message: str, at: datetime) -> Changed:
    done = tuple(agent for agent in board.at_work if agent.id == agent_id)
    if not done:
        return board, None
    left = tuple(agent for agent in board.at_work if agent.id != agent_id)
    finished = (*board.finished, Finished(agent=done[0], ended=at, last_message=last_message))
    return Board(at_work=left, finished=finished[-KEPT_FINISHED:]), AgentsChanged(at_work=len(left), finished=True)


def describe(board: Board, tasks: tuple[Task, ...]) -> Board:
    descriptions = {task.id: task.description for task in tasks if task.description}
    return replace(
        board,
        at_work=tuple(
            replace(agent, description=descriptions.get(agent.id, agent.description)) for agent in board.at_work
        ),
    )
