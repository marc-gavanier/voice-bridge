from dataclasses import dataclass
from typing import TYPE_CHECKING, assert_never

from voice_bridge.features.hearing.domain.utterance import (
    Dismissed,
    Frame,
    Kept,
    Listening,
    UtteranceRules,
    close,
    hear,
    is_speaking,
    needs_turn_check,
    silent_for,
    turn_checked,
    utterance_audio,
)

if TYPE_CHECKING:
    from voice_bridge.features.hearing.abilities.listen.domain.ports import Judge


@dataclass(frozen=True, slots=True, kw_only=True)
class Turn:
    judge: Judge
    threshold: float


@dataclass(frozen=True, slots=True, kw_only=True)
class VoiceStarted:
    at: float


@dataclass(frozen=True, slots=True, kw_only=True)
class Speaking:
    at: float


@dataclass(frozen=True, slots=True, kw_only=True)
class Utterance:
    pcm: bytes
    ended: float


@dataclass(frozen=True, slots=True, kw_only=True)
class TurnChecked:
    probability: float
    pause: float
    finished: bool


type Heard = VoiceStarted | Speaking | Utterance | Dismissed | TurnChecked


def _judged(
    listening: Listening, now: float, rules: UtteranceRules, turn: Turn | None
) -> tuple[Listening, tuple[TurnChecked, ...]]:
    if turn is None or not needs_turn_check(listening, now, rules):
        return listening, ()
    probability = turn.judge(utterance_audio(listening))
    checked = TurnChecked(
        probability=probability, pause=silent_for(listening, now), finished=probability > turn.threshold
    )
    return turn_checked(listening, finished=checked.finished), (checked,)


def paused(
    listening: Listening, now: float, rules: UtteranceRules, turn: Turn | None
) -> tuple[Listening, tuple[Heard, ...]]:
    judged, checks = _judged(listening, now, rules, turn)
    finished = any(check.finished for check in checks)
    remaining, closing = close(judged, now, rules, finished=finished)
    match closing:
        case Kept(pcm=pcm, ended=ended):
            return remaining, (*checks, Utterance(pcm=pcm, ended=ended))
        case Dismissed():
            return remaining, (*checks, closing)
        case None:
            return remaining, checks
        case _:
            assert_never(closing)


def heard_frame(
    listening: Listening, frame: Frame, rules: UtteranceRules, turn: Turn | None
) -> tuple[Listening, tuple[Heard, ...]]:
    hearing = hear(listening, frame, rules)
    started = (VoiceStarted(at=frame.at),) if hearing.utterance and not listening.utterance else ()
    speaking = (Speaking(at=frame.at),) if is_speaking(hearing, rules) else ()
    remaining, closed = paused(hearing, frame.at, rules, turn)
    return remaining, (*started, *speaking, *closed)
