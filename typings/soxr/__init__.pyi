from typing import Literal

import numpy as np
import numpy.typing as npt

type Quality = Literal["QQ", "LQ", "MQ", "HQ", "VHQ"]

__version__: str

def resample(
    x: npt.NDArray[np.float32], in_rate: float, out_rate: float, quality: Quality = "HQ"
) -> npt.NDArray[np.float32]: ...

class ResampleStream:
    def __init__(
        self,
        in_rate: float,
        out_rate: float,
        num_channels: int,
        dtype: Literal["float32"] = "float32",
        quality: Quality = "HQ",
        vr: bool = False,
    ) -> None: ...
    def resample_chunk(self, x: npt.NDArray[np.float32], last: bool = False) -> npt.NDArray[np.float32]: ...
