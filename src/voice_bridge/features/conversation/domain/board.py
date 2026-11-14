from dataclasses import dataclass, replace
from datetime import timedelta
from typing import TYPE_CHECKING, Final

from voice_bridge.features.conversation.domain.turn_taking import AgentsChanged

if TYPE_CHECKING:
    from datetime import datetime

KEPT_FINISHED: Final = 20
TOLERATED_SILENCE: Final = timedelta(seconds=30)


@dataclass(frozen=True, slots=True, kw_only=True)
class Agent:
    id: str
    kind: str
    since: datetime
    description: str = ""
    background: bool = False
    resumed: int = 0
    resumed_at: datetime | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class Finished:
    agent: Agent
    ended: datetime
    last_message: str


@dataclass(frozen=True, slots=True, kw_only=True)
class Task:
    id: str
    description: str
    kind: str = ""


@dataclass(frozen=True, slots=True, kw_only=True)
class Board:
    at_work: tuple[Agent, ...] = ()
    finished: tuple[Finished, ...] = ()
    unheard_since: datetime | None = None
    gap_since: datetime | None = None


type Changed = tuple[Board, AgentsChanged | None]


def _resumed(paused: Finished, at: datetime) -> Agent:
    return replace(paused.agent, resumed=paused.agent.resumed + 1, resumed_at=at)


def start(board: Board, *, agent_id: str, kind: str, at: datetime) -> Changed:
    if not kind or any(agent.id == agent_id for agent in board.at_work):
        return board, None
    paused = tuple(finished for finished in board.finished if finished.agent.id == agent_id)
    agent = _resumed(paused[0], at) if paused else Agent(id=agent_id, kind=kind, since=at)
    started = replace(
        board,
        at_work=(*board.at_work, agent),
        finished=tuple(finished for finished in board.finished if finished.agent.id != agent_id),
    )
    return started, AgentsChanged(at_work=len(started.at_work))


def finish(board: Board, *, agent_id: str, last_message: str, at: datetime) -> Changed:
    done = tuple(agent for agent in board.at_work if agent.id == agent_id)
    if not done:
        return board, None
    left = tuple(agent for agent in board.at_work if agent.id != agent_id)
    finished = (*board.finished, Finished(agent=done[0], ended=at, last_message=last_message))
    return replace(board, at_work=left, finished=finished[-KEPT_FINISHED:]), AgentsChanged(at_work=len(left))


def _listed(agent: Agent, running: dict[str, Task]) -> Agent:
    task = running.get(agent.id)
    if task is None:
        return agent
    return replace(agent, background=True, description=task.description or agent.description)


def _new(task: Task, at: datetime) -> Agent:
    return Agent(id=task.id, kind=task.kind, since=at, description=task.description, background=True)


def reconcile(board: Board, running: tuple[Task, ...], *, at: datetime, leaving: str) -> Changed:
    listed = {task.id: task for task in running}
    stays = tuple(agent for agent in board.at_work if not agent.background or agent.id in listed or agent.id == leaving)
    ended = tuple(Finished(agent=agent, ended=at, last_message="") for agent in board.at_work if agent not in stays)
    known = {leaving, *(agent.id for agent in board.at_work), *(done.agent.id for done in board.finished)}
    added = tuple(_new(task, at) for task in listed.values() if task.kind and task.id not in known)
    reconciled = replace(
        board,
        at_work=(*(_listed(agent, listed) for agent in stays), *added),
        finished=(*board.finished, *ended)[-KEPT_FINISHED:],
        gap_since=None,
    )
    if len(reconciled.at_work) == len(board.at_work):
        return reconciled, None
    return reconciled, AgentsChanged(at_work=len(reconciled.at_work))


def _too_long(since: datetime | None, now: datetime) -> bool:
    return since is not None and now - since > TOLERATED_SILENCE


def forwarded(board: Board, *, at: datetime) -> Board:
    return replace(board, unheard_since=board.unheard_since or at)


def heard(board: Board, *, at: datetime) -> Board:
    gap = board.unheard_since if _too_long(board.unheard_since, at) else board.gap_since
    return replace(board, unheard_since=None, gap_since=gap)


def unreliable_since(board: Board, *, now: datetime) -> datetime | None:
    if board.gap_since is not None:
        return board.gap_since
    return board.unheard_since if _too_long(board.unheard_since, now) else None
