from collections.abc import Callable

import pytest

from voice_bridge.configuration.language import language_pack
from voice_bridge.configuration.settings import Language

type RouteOf = Callable[[Language, str], str]


def test_hindi_is_spoken_with_a_hindi_voice() -> None:
    assert language_pack("hi").voice == "hi_female"


def test_hindi_greets_in_hindi() -> None:
    assert "मैं सुन रही हूँ।" in language_pack("hi").greetings


@pytest.mark.parametrize(
    ("words", "expected"),
    [
        ("रुको, क्या तुम अभी रुक सकते हो?", "stop"),
        ("क्या तुम मुझे ठीक से सुन रहे हो?", "presence"),
        ("बहुत बहुत धन्यवाद, बढ़िया बना है।", "thanks"),
        ("कल मिलते हैं, शुभ रात्रि।", "end"),
        ("क्या तुम टेस्ट चला सकते हो?", "request"),
        ("हाँ, ऐसे ही करते हैं।", "go_ahead"),
        ("तुमने बहुत अच्छा काम किया।", "compliment"),
        ("हाँ, ऐसे ही ठीक है।", "yes"),
        ("हाँ, कर दो।", "go_ahead"),
        ("मुझे अभी एक आइडिया आया…", "idea_coming"),
        ("इसके लिए बहुत धन्यवाद।", "thanks"),
        ("मैंने ऐप फिर से चालू किया।", "presence"),
        ("आज के लिए यहीं रुकते हैं।", "end"),
        ("तुमने सच में बढ़िया काम किया है।", "compliment"),
        ("मदद के लिए धन्यवाद।", "thanks"),
        ("चलो, तुम इसे चला सकते हो।", "go_ahead"),
        ("हाँ, ऐसे मुझे ठीक लगता है।", "yes"),
        ("रुको, मुझे अभी कुछ सूझा।", "idea_coming"),
        ("हम कोई दूसरा टूल इस्तेमाल कर सकते हैं।", "idea"),
        ("ठीक है, मैंने फिर से शुरू कर दिया।", "presence"),
        ("अभी के लिए यहीं रुकते हैं।", "end"),
        ("छोड़ो, ढूँढना बंद करो।", "stop"),
        ("अरे, क्या तुम वहीं रुक सकते हो?", "stop"),
        ("रुको!", "stop"),
        ("नहीं।", "no"),
        ("तो, अगला कदम क्या है?", "question"),
    ],
)
def test_hindi_words_take_the_route_of_their_meaning(words: str, expected: str, route_of: RouteOf) -> None:
    assert route_of("hi", words) == expected


@pytest.mark.parametrize(
    "words",
    [
        "क्या तुमने देखा कि यह ठीक से रुका या नहीं?",
        "चलो, शुरू करते हैं।",
        "इसे ऐसे ही रहने दो।",
        "मैंने रुको नहीं कहा, तुम बस बहुत तेज़ थे।",
        "हाँ, यह ठीक से रुक गया।",
        "क्या तुम्हें पूरा लेख पढ़ने का समय मिला या तुम पहले रुक गए?",
        "ठीक है, रुकने वाले हिस्से से शुरू करते हैं।",
        "जैसा है वैसा रहने दो, अच्छा है।",
        "यहीं रुकते हैं।",
        "नहीं, इसे ऐसे ही रहने दो।",
    ],
)
def test_hindi_words_about_stopping_do_not_stop(words: str, route_of: RouteOf) -> None:
    assert route_of("hi", words) != "stop"
