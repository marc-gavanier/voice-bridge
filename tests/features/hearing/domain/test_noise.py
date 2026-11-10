import pytest

from voice_bridge.features.hearing.domain.noise import Hallucinations, is_noise

FRENCH = Hallucinations(texts=frozenset({"", "merci", "je vous prie"}), prefixes=("sous-titrage",))


@pytest.mark.parametrize(
    "text", ["", "  ", "Merci.", "merci", "- Merci.", "\N{EN DASH} Sous-titrage ST' 501", "Je vous prie."]
)
def test_empty_text_and_whisper_hallucinations_are_noise(text: str) -> None:
    assert is_noise(text, FRENCH)


@pytest.mark.parametrize("text", ["Merci, on continue.", "Est-ce que tu m'entends ?"])
def test_real_speech_is_not_noise(text: str) -> None:
    assert not is_noise(text, FRENCH)
