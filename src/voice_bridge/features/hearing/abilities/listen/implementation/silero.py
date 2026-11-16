from dataclasses import dataclass, field, replace
from functools import reduce
from typing import TYPE_CHECKING, Final, Protocol

import numpy as np
import numpy.typing as npt
import onnxruntime as ort
import pooch
import soxr

from voice_bridge.libraries.audio.pcm import Samples, to_float

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

SILERO_RATE: Final = 16000
WINDOW: Final = 512
CONTEXT: Final = 64
STATE_SHAPE: Final = (2, 1, 128)
MODEL_URL: Final = (
    "https://raw.githubusercontent.com/snakers4/silero-vad/"
    "4c00cd14be0ff5b8bd6846a6eec72741aac837f2/src/silero_vad/data/silero_vad.onnx"
)
MODEL_HASH: Final = "sha256:597d30b3ec076608d059477bb14cfeffdf951bf5cae370d38f65d33bbfe82004"
_RATE_INPUT: Final = np.array(SILERO_RATE, dtype=np.int64)


class Session(Protocol):
    def run(
        self, output_names: None, input_feed: Mapping[str, npt.NDArray[np.float32] | npt.NDArray[np.int64]]
    ) -> Sequence[npt.NDArray[np.float32]]: ...


def load_silero() -> Session:
    options = ort.SessionOptions()
    options.inter_op_num_threads = 1
    options.intra_op_num_threads = 1
    options.enable_cpu_mem_arena = False
    options.log_severity_level = 4
    path = pooch.retrieve(MODEL_URL, known_hash=MODEL_HASH, progressbar=False)
    return ort.InferenceSession(path, sess_options=options, providers=["CPUExecutionProvider"])


def _zeros(*shape: int) -> npt.NDArray[np.float32]:
    return np.zeros(shape, dtype=np.float32)


@dataclass(frozen=True, slots=True, kw_only=True)
class Silero:
    pending: Samples = field(default_factory=lambda: _zeros(0))
    context: npt.NDArray[np.float32] = field(default_factory=lambda: _zeros(1, CONTEXT))
    state: npt.NDArray[np.float32] = field(default_factory=lambda: _zeros(*STATE_SHAPE))
    probability: float = 0.0


def _score(session: Session, state: Silero, window: Samples) -> Silero:
    framed = np.concatenate([state.context, window.reshape(1, WINDOW)], axis=1)
    output, after = session.run(None, {"input": framed, "state": state.state, "sr": _RATE_INPUT})
    return replace(state, context=framed[:, -CONTEXT:], state=after, probability=float(np.max(output)))


def listen(session: Session, state: Silero, pcm: bytes, rate: int) -> Silero:
    samples = np.concatenate([state.pending, soxr.resample(to_float(pcm), rate, SILERO_RATE)])
    usable = samples.size // WINDOW * WINDOW
    scored = reduce(
        lambda current, window: _score(session, current, window), samples[:usable].reshape(-1, WINDOW), state
    )
    return replace(scored, pending=samples[usable:])


@dataclass(slots=True, kw_only=True)
class SileroDetector:
    session: Session
    rate: int
    state: Silero = field(default_factory=Silero)

    def __call__(self, pcm: bytes, /) -> float:
        self.state = listen(self.session, self.state, pcm, self.rate)
        return self.state.probability
