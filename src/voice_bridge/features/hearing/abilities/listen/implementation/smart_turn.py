import math
from typing import TYPE_CHECKING, Final, Protocol

import numpy as np
import numpy.typing as npt
import onnxruntime as ort
import soxr
from faster_whisper.feature_extractor import FeatureExtractor
from huggingface_hub import hf_hub_download

from voice_bridge.libraries.audio.pcm import Samples, to_float

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

SMART_TURN_RATE: Final = 16000
SECONDS: Final = 8
MEL_BINS: Final = 80
FRAMES: Final = 800
REPOSITORY: Final = "pipecat-ai/smart-turn-v3"
MODEL_FILE: Final = "smart-turn-v3.2-cpu.onnx"
REVISION: Final = "f766f81d3cfdf7737ac64aad813d91bbfd56bf93"
NORMALIZATION_FLOOR: Final = 1e-7

_EXTRACTOR: Final = FeatureExtractor(feature_size=MEL_BINS, sampling_rate=SMART_TURN_RATE, chunk_length=SECONDS)


class Session(Protocol):
    def run(
        self, output_names: None, input_feed: Mapping[str, npt.NDArray[np.float32]]
    ) -> Sequence[npt.NDArray[np.float32]]: ...


def load_session() -> Session:
    options = ort.SessionOptions()
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    options.inter_op_num_threads = 1
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    path = hf_hub_download(REPOSITORY, MODEL_FILE, revision=REVISION)
    return ort.InferenceSession(path, sess_options=options, providers=["CPUExecutionProvider"])


def _last_seconds(samples: Samples) -> Samples:
    size = SECONDS * SMART_TURN_RATE
    return np.pad(samples[-size:], (max(0, size - samples.size), 0))


def _normalized(samples: Samples) -> Samples:
    spread = math.sqrt(float(np.var(samples)) + NORMALIZATION_FLOOR)
    return ((samples - float(np.mean(samples))) / spread).astype(np.float32)


def features(pcm: bytes, rate: int) -> npt.NDArray[np.float32]:
    samples = _normalized(_last_seconds(soxr.resample(to_float(pcm), rate, SMART_TURN_RATE)))
    return _EXTRACTOR(samples, padding=0)[np.newaxis, :, :FRAMES].astype(np.float32)


def completion(session: Session, pcm: bytes, rate: int) -> float:
    return float(np.max(session.run(None, {"input_features": features(pcm, rate)})[0]))
