from typing import TYPE_CHECKING, Final

import av
import av.error
import av.filter
import numpy as np

if TYPE_CHECKING:
    from collections.abc import Iterator

METHOD: Final = "atempo"
NATURAL_PACE: Final = 1.0


def _frame(pcm: bytes, rate: int) -> av.AudioFrame:
    frame = av.AudioFrame.from_ndarray(np.frombuffer(pcm, dtype=np.int16).reshape(1, -1), format="s16", layout="mono")
    frame.sample_rate = rate
    return frame


def _drained(graph: av.filter.Graph) -> Iterator[bytes]:
    while True:
        try:
            frame = graph.pull()
        except av.error.EOFError:
            return
        yield frame.to_ndarray().tobytes()


def stretch(pcm: bytes, rate: int, factor: float) -> bytes:
    if factor == NATURAL_PACE or not pcm:
        return pcm
    graph = av.filter.Graph()
    _ = graph.link_nodes(
        graph.add_abuffer(format="s16", sample_rate=rate, layout="mono"),
        graph.add(METHOD, str(factor)),
        graph.add("abuffersink"),
    )
    graph.configure()
    graph.push(_frame(pcm, rate))
    graph.push(None)
    return b"".join(_drained(graph))
