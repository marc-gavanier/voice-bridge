from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, Protocol

import numpy as np
import numpy.typing as npt
import onnxruntime as ort
from huggingface_hub import hf_hub_download
from tokenizers import Tokenizer

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

REPOSITORY: Final = "Qdrant/paraphrase-multilingual-MiniLM-L12-v2-onnx-Q"
MODEL_FILE: Final = "model_optimized.onnx"
TOKENIZER_FILE: Final = "tokenizer.json"
REVISION: Final = "faf4aa4225822f3bc6376869cb1164e8e3feedd0"
LONGEST: Final = 128

type Vectors = npt.NDArray[np.float32]


class Session(Protocol):
    def run(
        self, output_names: None, input_feed: Mapping[str, npt.NDArray[np.int64]]
    ) -> Sequence[npt.NDArray[np.float32]]: ...


class Embed(Protocol):
    def __call__(self, texts: Sequence[str]) -> Vectors: ...


def _row_sums(matrix: Vectors) -> Vectors:
    return (matrix @ np.ones_like(matrix[:1]).T)[:, 0]


def _normalized(vectors: Vectors) -> Vectors:
    lengths = np.sqrt(_row_sums(vectors * vectors)).astype(np.float32)
    return (vectors / lengths[:, np.newaxis]).astype(np.float32)


@dataclass(frozen=True, slots=True)
class Encoder:
    session: Session
    tokenizer: Tokenizer

    def __call__(self, texts: Sequence[str]) -> Vectors:
        encodings = self.tokenizer.encode_batch(list(texts))
        ids = np.array([encoding.ids for encoding in encodings], dtype=np.int64)
        mask = np.array([encoding.attention_mask for encoding in encodings], dtype=np.int64)
        feed = {"input_ids": ids, "attention_mask": mask, "token_type_ids": np.zeros_like(ids)}
        tokens = self.session.run(None, feed)[0]
        weights = mask.astype(np.float32)
        summed = (weights[:, np.newaxis, :] @ tokens)[:, 0, :]
        counts = np.maximum(_row_sums(weights), np.float32(1.0))
        return _normalized((summed / counts[:, np.newaxis]).astype(np.float32))


def load_encoder() -> Encoder:
    options = ort.SessionOptions()
    options.inter_op_num_threads = 1
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    model = hf_hub_download(REPOSITORY, MODEL_FILE, revision=REVISION)
    tokenizer = Tokenizer.from_file(hf_hub_download(REPOSITORY, TOKENIZER_FILE, revision=REVISION))
    tokenizer.enable_truncation(max_length=LONGEST)
    tokenizer.enable_padding()
    return Encoder(
        session=ort.InferenceSession(model, sess_options=options, providers=["CPUExecutionProvider"]),
        tokenizer=tokenizer,
    )


@dataclass(frozen=True, slots=True)
class Router:
    embed: Embed
    examples: Vectors
    owners: npt.NDArray[np.intp]
    routes: int

    def __call__(self, text: str) -> list[float]:
        similarities = (self.examples @ self.embed([text]).T)[:, 0]
        best = np.full(self.routes, -1.0, dtype=np.float32)
        np.maximum.at(best, self.owners, similarities)
        return [float(score) for score in best]


def router(embed: Embed, examples: Sequence[Sequence[str]]) -> Router:
    owners = np.array([index for index, route in enumerate(examples) for _ in route], dtype=np.intp)
    return Router(
        embed=embed,
        examples=embed([example for route in examples for example in route]),
        owners=owners,
        routes=len(examples),
    )
