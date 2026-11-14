from datetime import UTC, datetime, timedelta
from functools import reduce
from itertools import pairwise

from hypothesis import given
from hypothesis import strategies as st

from voice_bridge.features.conversation.domain.board import (
    KEPT_FINISHED,
    Agent,
    Board,
    Changed,
    Task,
    act,
    finish,
    reconcile,
    start,
)
from voice_bridge.features.conversation.domain.turn_taking import AgentsChanged

MORNING = datetime(2026, 11, 13, 9, 0, tzinfo=UTC)
IDS = st.sampled_from(["a1", "a2", "a3", "a4"])
KINDS = st.sampled_from(["", "general-purpose"])
type Move = tuple[str, str, str, tuple[Task, ...]]
TASKS = st.lists(st.builds(Task, id=IDS, description=st.just("Search"), kind=KINDS), max_size=4).map(tuple)
MOVES = st.lists(st.tuples(st.sampled_from(["start", "finish", "reconcile"]), IDS, KINDS, TASKS), max_size=40)


def moved(board: Board, move: Move) -> Changed:
    name, agent_id, kind, running = move
    if name == "start":
        return start(board, agent_id=agent_id, kind=kind, at=MORNING)
    if name == "finish":
        return finish(board, agent_id=agent_id, last_message=kind, at=MORNING)
    return reconcile(board, running, at=MORNING, leaving=agent_id if kind else "")


def history(moves: list[Move]) -> list[Changed]:
    def advance(changes: list[Changed], move: Move) -> list[Changed]:
        return [*changes, moved(changes[-1][0], move)]

    return reduce(advance, moves, [(Board(), None)])


def miscounted(changes: list[Changed]) -> list[tuple[AgentsChanged, int]]:
    return [
        (change, len(board.at_work)) for board, change in changes if change and change.at_work != len(board.at_work)
    ]


@given(MOVES)
def test_every_change_announces_the_agents_left_at_work(moves: list[Move]) -> None:
    assert miscounted(history(moves)) == []


def duplicated(changes: list[Changed]) -> list[Board]:
    return [board for board, _ in changes if len({agent.id for agent in board.at_work}) != len(board.at_work)]


@given(MOVES)
def test_an_agent_is_never_at_work_twice(moves: list[Move]) -> None:
    assert duplicated(history(moves)) == []


def ids_on(board: Board) -> list[str]:
    return [agent.id for agent in board.at_work] + [finished.agent.id for finished in board.finished]


def listed_twice(changes: list[Changed]) -> list[Board]:
    return [board for board, _ in changes if len(set(ids_on(board))) != len(ids_on(board))]


@given(MOVES)
def test_an_agent_appears_at_most_once_on_the_board(moves: list[Move]) -> None:
    assert listed_twice(history(moves)) == []


@given(MOVES)
def test_the_finished_agents_kept_never_exceed_the_limit(moves: list[Move]) -> None:
    assert len(history(moves)[-1][0].finished) <= KEPT_FINISHED


type Action = tuple[str, int]
ACTIONS = st.lists(st.tuples(IDS, st.integers(min_value=0, max_value=600)), max_size=40)
STARTED = Board(
    at_work=tuple(Agent(id=agent_id, kind="Explore", since=MORNING) for agent_id in ("a1", "a2", "a3", "a4"))
)
NEVER = MORNING - timedelta(days=1)


def acted(board: Board, action: Action) -> Board:
    agent_id, seconds = action
    return act(board, agent_id=agent_id, action=f"Bash {seconds}", at=MORNING + timedelta(seconds=seconds))


def boards_acted(actions: list[Action]) -> list[Board]:
    return reduce(lambda boards, action: [*boards, acted(boards[-1], action)], actions, [STARTED])


def moments(board: Board) -> dict[str, datetime]:
    return {agent.id: agent.last_action_at or NEVER for agent in board.at_work}


def went_back(before: Board, after: Board) -> list[str]:
    return [agent_id for agent_id, moment in moments(before).items() if moments(after)[agent_id] < moment]


def gone_back(boards: list[Board]) -> list[list[str]]:
    return [went_back(before, after) for before, after in pairwise(boards) if went_back(before, after)]


@given(ACTIONS)
def test_the_latest_action_of_an_agent_never_goes_back_in_time(actions: list[Action]) -> None:
    assert gone_back(boards_acted(actions)) == []
