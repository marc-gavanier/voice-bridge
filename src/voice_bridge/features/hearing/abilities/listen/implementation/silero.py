from dataclasses import dataclass, field, replace
from functools import reduce
from typing import TYPE_CHECKING, Final, Protocol

import numpy as np
import numpy.typing as npt
import soxr

from voice_bridge.libraries.audio.pcm import Samples, level, to_float

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

SILERO_RATE: Final = 16000
WINDOW: Final = 512
CONTEXT: Final = 64
STATE_SHAPE: Final = (1, 1, 128)


class Session(Protocol):
    def run(
        self, output_names: None, input_feed: Mapping[str, npt.NDArray[np.float32]]
    ) -> Sequence[npt.NDArray[np.float32]]: ...


def _zeros(*shape: int) -> npt.NDArray[np.float32]:
    return np.zeros(shape, dtype=np.float32)


@dataclass(frozen=True, slots=True, kw_only=True)
class Silero:
    pending: Samples = field(default_factory=lambda: _zeros(0))
    context: npt.NDArray[np.float32] = field(default_factory=lambda: _zeros(1, CONTEXT))
    h: npt.NDArray[np.float32] = field(default_factory=lambda: _zeros(*STATE_SHAPE))
    c: npt.NDArray[np.float32] = field(default_factory=lambda: _zeros(*STATE_SHAPE))
    probability: float = 0.0


@dataclass(frozen=True, slots=True, kw_only=True)
class Voicing:
    volume_threshold: float
    probability: float


def _score(session: Session, state: Silero, window: Samples) -> Silero:
    framed = np.concatenate([state.context, window.reshape(1, WINDOW)], axis=1)
    output, h, c = session.run(None, {"input": framed, "h": state.h, "c": state.c})
    return replace(state, context=framed[:, -CONTEXT:], h=h, c=c, probability=float(np.max(output)))


def listen(session: Session, state: Silero, pcm: bytes, rate: int) -> Silero:
    samples = np.concatenate([state.pending, soxr.resample(to_float(pcm), rate, SILERO_RATE)])
    usable = samples.size // WINDOW * WINDOW
    scored = reduce(
        lambda current, window: _score(session, current, window), samples[:usable].reshape(-1, WINDOW), state
    )
    return replace(scored, pending=samples[usable:])


def is_voiced(state: Silero, pcm: bytes, voicing: Voicing) -> bool:
    return state.probability >= voicing.probability and level(pcm) >= voicing.volume_threshold
