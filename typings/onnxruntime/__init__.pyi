from collections.abc import Mapping, Sequence
from enum import Enum

import numpy as np
import numpy.typing as npt

class ExecutionMode(Enum):
    ORT_SEQUENTIAL = 0

class GraphOptimizationLevel(Enum):
    ORT_ENABLE_ALL = 99

class SessionOptions:
    execution_mode: ExecutionMode
    inter_op_num_threads: int
    intra_op_num_threads: int
    graph_optimization_level: GraphOptimizationLevel

class InferenceSession:
    def __init__(
        self, path_or_bytes: str, sess_options: SessionOptions | None = None, providers: Sequence[str] | None = None
    ) -> None: ...
    def run(
        self, output_names: None, input_feed: Mapping[str, npt.NDArray[np.float32] | npt.NDArray[np.int64]]
    ) -> Sequence[npt.NDArray[np.float32]]: ...
