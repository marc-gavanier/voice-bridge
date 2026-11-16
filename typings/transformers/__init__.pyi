import numpy as np
import numpy.typing as npt

class BatchFeature:
    def __getitem__(self, item: str) -> npt.NDArray[np.float32]: ...

class WhisperFeatureExtractor:
    def __init__(
        self,
        feature_size: int = 80,
        sampling_rate: int = 16000,
        hop_length: int = 160,
        chunk_length: int = 30,
        n_fft: int = 400,
    ) -> None: ...
    def __call__(
        self,
        raw_speech: npt.NDArray[np.float32],
        *,
        sampling_rate: int | None = None,
        return_tensors: str | None = None,
    ) -> BatchFeature: ...
