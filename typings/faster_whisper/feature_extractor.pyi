import numpy as np
import numpy.typing as npt

class FeatureExtractor:
    def __init__(
        self,
        feature_size: int = 80,
        sampling_rate: int = 16000,
        hop_length: int = 160,
        chunk_length: int = 30,
        n_fft: int = 400,
    ) -> None: ...
    def __call__(
        self, waveform: npt.NDArray[np.float32], padding: int = 160, chunk_length: int | None = None
    ) -> npt.NDArray[np.float32]: ...
