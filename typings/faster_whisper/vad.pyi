from collections.abc import Mapping, Sequence

import numpy as np
import numpy.typing as npt

class InferenceSession:
    def run(
        self, output_names: None, input_feed: Mapping[str, npt.NDArray[np.float32]]
    ) -> Sequence[npt.NDArray[np.float32]]: ...

class SileroVADModel:
    session: InferenceSession

def get_vad_model() -> SileroVADModel: ...
