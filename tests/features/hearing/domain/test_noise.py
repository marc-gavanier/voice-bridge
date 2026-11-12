import pytest

from voice_bridge.features.hearing.domain.noise import Hallucinations, is_noise

HALLUCINATIONS = Hallucinations(texts=frozenset({"", "thank you", "you"}), prefixes=("subtitles by",))


@pytest.mark.parametrize(
    "text",
    ["", "  ", "Thank you.", "thank you", "- Thank you.", "\N{EN DASH} Subtitles by the Amara.org community", "You."],
)
def test_empty_text_and_whisper_hallucinations_are_noise(text: str) -> None:
    assert is_noise(text, HALLUCINATIONS)


@pytest.mark.parametrize("text", ["Thank you, let us go on.", "Can you hear me?", "Thank you X."])
def test_real_speech_is_not_noise(text: str) -> None:
    assert not is_noise(text, HALLUCINATIONS)
