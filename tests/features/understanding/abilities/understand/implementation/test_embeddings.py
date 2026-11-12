from collections.abc import Sequence

import numpy as np

from voice_bridge.features.understanding.abilities.understand.implementation.embeddings import (
    Vectors,
    load_encoder,
    router,
)

AXES = {"stop": (1.0, 0.0), "yes": (0.0, 1.0), "meh": (0.6, 0.8)}


def along_axes(texts: Sequence[str]) -> Vectors:
    return np.array([AXES[text] for text in texts], dtype=np.float32)


def test_each_route_scores_its_closest_example() -> None:
    assert router(along_axes, [["stop", "meh"], ["yes"]])("meh") == [1.0, 0.800000011920929]


def test_a_route_scores_by_cosine_similarity() -> None:
    assert router(along_axes, [["stop"], ["yes"]])("stop") == [1.0, 0.0]


def test_the_encoder_gives_unit_vectors() -> None:
    vectors = load_encoder()(["Stop.", "Can you hear me?"])
    assert np.allclose((vectors * vectors) @ np.ones_like(vectors[:1]).T, 1.0)


def test_the_encoder_puts_a_stop_closer_to_a_stop_than_to_thanks() -> None:
    scores = router(load_encoder(), [["Stop everything."], ["Thank you very much."]])("Stop, can you stop?")
    assert scores[0] > scores[1]
