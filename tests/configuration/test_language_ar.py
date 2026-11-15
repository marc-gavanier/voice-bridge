from collections.abc import Callable

import pytest

from voice_bridge.configuration.language import language_pack
from voice_bridge.configuration.settings import Language

type RouteOf = Callable[[Language, str], str]


def test_arabic_is_spoken_with_a_arabic_voice() -> None:
    assert language_pack("ar").voice == "ar_male"


def test_arabic_greets_in_arabic() -> None:
    assert "أنا أسمعك." in language_pack("ar").greetings


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
        ("نعم، لنفعلها هكذا.", "go_ahead"),
        ("لقد قمت بعمل جيد جدًا.", "compliment"),
        ("نعم، هذا جيد هكذا.", "yes"),
        ("نعم، افعلها.", "go_ahead"),
        ("خطرت لي فكرة للتو…", "idea_coming"),
        ("شكرًا جزيلًا على ذلك.", "thanks"),
        ("أعدت تشغيل التطبيق.", "presence"),
        ("نتوقف هنا لليوم.", "end"),
        ("لقد قمت بعمل رائع حقًا.", "compliment"),
        ("شكرًا على المساعدة يا صديقي.", "thanks"),
        ("هيا، يمكنك تشغيله.", "go_ahead"),
        ("نعم، هكذا يناسبني.", "yes"),
        ("انتظر، خطرت ببالي فكرة الآن.", "idea_coming"),
        ("يمكننا استخدام أداة أخرى.", "idea"),
        ("حسنًا، أعدت التشغيل.", "presence"),
        ("نتوقف هنا الآن.", "end"),
        ("انسَ الأمر، توقف عن البحث.", "stop"),
        ("هل يمكنك أن تتوقف هنا؟", "stop"),
        ("توقف!", "stop"),
        ("لا.", "no"),
        ("إذن، ما هي الخطوة التالية؟", "question"),
        ("نعم، توقف.", "stop"),
    ],
)
def test_arabic_words_take_the_route_of_their_meaning(words: str, expected: str, route_of: RouteOf) -> None:
    assert route_of("ar", words) == expected


@pytest.mark.parametrize(
    "words",
    [
        "هل رأيت إن كان قد توقف جيدًا؟",
        "هيا، لنبدأ.",
        "نتركه هكذا.",
        "لم أقل توقف، أنت فقط كنت سريعًا جدًا.",
        "نعم، لقد توقف بشكل صحيح.",
        "هل كان لديك وقت لإنهاء المقال أم توقفت قبل ذلك؟",
        "حسنًا، نبدأ بجزء التوقف.",
        "اتركه هكذا، هذا جيد.",
        "نتوقف هنا.",
        "لا، نتركه كما هو.",
    ],
)
def test_arabic_words_about_stopping_do_not_stop(words: str, route_of: RouteOf) -> None:
    assert route_of("ar", words) != "stop"
