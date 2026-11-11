from collections.abc import Sequence

import pytest

from voice_bridge.features.speaking.abilities.acknowledge import AcknowledgementRule, Clips, record_acknowledgements

SOUND = b"\x01\x00" * 480
RULES: tuple[AcknowledgementRule, ...] = (
    (r"\?$", ("Voyons.", "Bonne question.")),
    (r"^non\b", ("Silencieux.",)),
    ("", ("D'accord.", "Silencieux.")),
)


def first(pool: Sequence[str]) -> str:
    return pool[0]


async def voiced(sentence: str) -> bytes | None:
    return None if sentence.startswith("Silencieux") else SOUND


async def recorded() -> Clips:
    clips = Clips(choose=first)
    await record_acknowledgements(clips, voiced, RULES)
    return clips


def test_no_clip_is_chosen_before_they_are_recorded() -> None:
    assert Clips(choose=first)("On en est où ?") is None


@pytest.mark.anyio
async def test_the_words_choose_the_kind_of_clip() -> None:
    assert (await recorded())("On en est où ?") == ("Voyons.", SOUND)


@pytest.mark.anyio
async def test_words_no_specific_rule_matches_get_the_last_rule_clip() -> None:
    assert (await recorded())("Le dépôt est propre.") == ("D'accord.", SOUND)


@pytest.mark.anyio
async def test_the_rules_ignore_case() -> None:
    assert (await recorded())("NON, ça va.") is None


@pytest.mark.anyio
async def test_a_kind_without_any_voiced_clip_plays_nothing() -> None:
    assert (await recorded())("Non, ça va.") is None


@pytest.mark.anyio
async def test_the_same_clip_is_not_played_twice_in_a_row() -> None:
    clips = await recorded()
    _ = clips("On en est où ?")
    assert clips("Et maintenant ?") == ("Bonne question.", SOUND)


@pytest.mark.anyio
async def test_a_sentence_without_voice_is_left_out() -> None:
    assert (await recorded()).pools[2] == {"D'accord.": SOUND}
