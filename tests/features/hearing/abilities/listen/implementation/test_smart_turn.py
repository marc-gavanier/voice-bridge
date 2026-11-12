import wave
from collections.abc import Mapping, Sequence
from pathlib import Path

import numpy as np
import numpy.typing as npt

from voice_bridge.features.hearing.abilities.listen.implementation.smart_turn import completion, features, load_session

RATE = 48000
SPEECH = Path(__file__).parents[5] / "fixtures" / "speech.wav"


def speech() -> bytes:
    with wave.open(str(SPEECH), "rb") as recording:
        return recording.readframes(recording.getnframes())


def test_the_features_cover_eight_seconds_of_whisper_frames() -> None:
    assert features(speech(), RATE).shape == (1, 80, 800)


def test_a_turn_longer_than_eight_seconds_keeps_its_end() -> None:
    long_turn = bytes(RATE * 2 * 10) + speech()
    assert np.allclose(features(long_turn, RATE), features(bytes(RATE * 2 * 6) + speech(), RATE), atol=1e-4)


def test_a_short_turn_is_padded_before_its_start() -> None:
    assert np.allclose(features(speech(), RATE), features(bytes(RATE * 2) + speech(), RATE), atol=1e-2)


class ThreeQuartersSure:
    def run(
        self, output_names: None, input_feed: Mapping[str, npt.NDArray[np.float32]]
    ) -> Sequence[npt.NDArray[np.float32]]:
        certainty = 0.75 if output_names is None else 0.0
        return [np.full((len(input_feed["input_features"]), 1), certainty, dtype=np.float32)]


def test_the_completion_is_the_probability_the_model_gives() -> None:
    assert completion(ThreeQuartersSure(), speech(), RATE) == 0.75


def test_a_whole_sentence_is_a_finished_turn() -> None:
    assert completion(load_session(), speech(), RATE) > 0.5
