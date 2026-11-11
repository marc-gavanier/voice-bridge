from collections.abc import Callable

import pytest

from voice_bridge.configuration.language import language_pack
from voice_bridge.configuration.settings import Language

type RouteOf = Callable[[Language, str], str]


def test_arabic_is_spoken_with_a_arabic_voice() -> None:
    assert language_pack("ar").voice == "ar_male"


def test_arabic_greets_in_arabic() -> None:
    assert language_pack("ar").greeting == "أنا أسمعك."


def test_arabic_knows_the_subtitle_credit_hallucination() -> None:
    assert "ترجمة نانسي قنقر" in language_pack("ar").hallucination_prefixes


@pytest.mark.parametrize(
    ("words", "expected"),
    [
        ("توقف، هل يمكنك التوقف الآن؟", "stop"),
        ("هل تسمعني جيدًا الآن؟", "presence"),
        ("شكرًا جزيلًا، النتيجة رائعة.", "thanks"),
        ("إلى الغد، تصبح على خير.", "end"),
        ("هل يمكنك تشغيل الاختبارات؟", "request"),
        ("نعم، لنفعلها هكذا.", "yes"),
    ],
)
def test_arabic_words_take_the_route_of_their_meaning(words: str, expected: str, route_of: RouteOf) -> None:
    assert route_of("ar", words) == expected


@pytest.mark.parametrize(
    "words",
    [
        "هل رأيت إن كان قد توقف جيدًا؟",
        "هيا، لنبدأ.",
    ],
)
def test_arabic_words_about_stopping_do_not_stop(words: str, route_of: RouteOf) -> None:
    assert route_of("ar", words) != "stop"
