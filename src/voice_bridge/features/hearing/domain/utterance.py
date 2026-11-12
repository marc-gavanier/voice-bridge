from dataclasses import dataclass, replace
from itertools import accumulate


@dataclass(frozen=True, slots=True, kw_only=True)
class Frame:
    pcm: bytes
    voiced: bool
    at: float
    duration: float


@dataclass(frozen=True, slots=True, kw_only=True)
class UtteranceRules:
    silence: float = 0.8
    longest: float = 30.0
    shortest_voice: float = 0.3
    preroll: float = 0.3
    barge_in: float = 0.5
    barge_window: float = 1.0
    short_pause: float | None = None
    unfinished_silence: float | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class Kept:
    pcm: bytes
    ended: float


@dataclass(frozen=True, slots=True, kw_only=True)
class Dismissed:
    voice: float
    duration: float


type Closing = Kept | Dismissed


@dataclass(frozen=True, slots=True, kw_only=True)
class Listening:
    utterance: tuple[Frame, ...] = ()
    preroll: tuple[Frame, ...] = ()
    recent: tuple[Frame, ...] = ()
    last_voice_at: float | None = None
    checked_at: float | None = None
    unfinished_at: float | None = None


def _duration(frames: tuple[Frame, ...]) -> float:
    return sum(frame.duration for frame in frames)


def _voice_duration(frames: tuple[Frame, ...]) -> float:
    return sum(frame.duration for frame in frames if frame.voiced)


def _latest(frames: tuple[Frame, ...], at_least: float) -> tuple[Frame, ...]:
    totals = accumulate(frame.duration for frame in reversed(frames))
    kept = next((count for count, total in enumerate(totals, start=1) if total >= at_least), len(frames))
    return frames[len(frames) - kept :]


def _on_voice(state: Listening, frame: Frame) -> Listening:
    start = state.utterance or state.preroll
    return replace(state, utterance=(*start, frame), preroll=(), last_voice_at=frame.at)


def _on_silence(state: Listening, frame: Frame, rules: UtteranceRules) -> Listening:
    if state.utterance:
        return replace(state, utterance=(*state.utterance, frame))
    return replace(state, preroll=_latest((*state.preroll, frame), rules.preroll))


def _within(frames: tuple[Frame, ...], now: float, window: float) -> tuple[Frame, ...]:
    return tuple(frame for frame in frames if now - frame.at < window)


def hear(state: Listening, frame: Frame, rules: UtteranceRules) -> Listening:
    remembered = replace(state, recent=_within((*state.recent, frame), frame.at, rules.barge_window))
    return _on_voice(remembered, frame) if frame.voiced else _on_silence(remembered, frame, rules)


def is_speaking(state: Listening, rules: UtteranceRules) -> bool:
    return _voice_duration(state.recent) >= rules.barge_in


def silent_for(state: Listening, now: float) -> float:
    return 0.0 if state.last_voice_at is None else now - state.last_voice_at


def utterance_audio(state: Listening) -> bytes:
    return b"".join(frame.pcm for frame in state.utterance)


def needs_turn_check(state: Listening, now: float, rules: UtteranceRules) -> bool:
    paused = rules.short_pause is not None and silent_for(state, now) >= rules.short_pause
    return bool(state.utterance) and paused and state.checked_at != state.last_voice_at


def turn_checked(state: Listening, *, finished: bool) -> Listening:
    return replace(state, checked_at=state.last_voice_at, unfinished_at=None if finished else state.last_voice_at)


def _silence(state: Listening, rules: UtteranceRules) -> float:
    unfinished = state.unfinished_at is not None and state.unfinished_at == state.last_voice_at
    if unfinished and rules.unfinished_silence is not None:
        return rules.unfinished_silence
    return rules.silence


def _is_over(state: Listening, now: float, rules: UtteranceRules) -> bool:
    return silent_for(state, now) > _silence(state, rules) or _duration(state.utterance) >= rules.longest


def close(
    state: Listening, now: float, rules: UtteranceRules, *, finished: bool = False
) -> tuple[Listening, Closing | None]:
    if not state.utterance or not (finished or _is_over(state, now, rules)):
        return state, None
    voice = _voice_duration(state.utterance)
    closing = (
        Kept(pcm=utterance_audio(state), ended=now if state.last_voice_at is None else state.last_voice_at)
        if voice >= rules.shortest_voice
        else Dismissed(voice=voice, duration=_duration(state.utterance))
    )
    return replace(state, utterance=(), recent=()), closing
