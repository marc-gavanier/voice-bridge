from collections.abc import Callable

import pytest

from voice_bridge.configuration.language import language_pack
from voice_bridge.configuration.settings import Language

type RouteOf = Callable[[Language, str], str]


def test_hindi_is_spoken_with_a_hindi_voice() -> None:
    assert language_pack("hi").voice == "hi_female"


def test_hindi_greets_in_hindi() -> None:
    assert language_pack("hi").greeting == "मैं सुन रही हूँ।"


@pytest.mark.parametrize(
    ("words", "expected"),
    [
        ("रुको, क्या तुम अभी रुक सकते हो?", "stop"),
        ("क्या तुम मुझे ठीक से सुन रहे हो?", "presence"),
        ("बहुत बहुत धन्यवाद, बढ़िया बना है।", "thanks"),
        ("कल मिलते हैं, शुभ रात्रि।", "end"),
        ("क्या तुम टेस्ट चला सकते हो?", "request"),
        ("हाँ, ऐसे ही करते हैं।", "yes"),
    ],
)
def test_hindi_words_take_the_route_of_their_meaning(words: str, expected: str, route_of: RouteOf) -> None:
    assert route_of("hi", words) == expected


@pytest.mark.parametrize(
    "words",
    [
        "क्या तुमने देखा कि यह ठीक से रुका या नहीं?",
        "चलो, शुरू करते हैं।",
    ],
)
def test_hindi_words_about_stopping_do_not_stop(words: str, route_of: RouteOf) -> None:
    assert route_of("hi", words) != "stop"
