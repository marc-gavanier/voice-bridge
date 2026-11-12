from collections.abc import Sequence

import pytest

from voice_bridge.features.speaking.abilities.acknowledge.domain.ports import Draw
from voice_bridge.features.speaking.abilities.acknowledge.implementation.acknowledge import (
    Clips,
    record_acknowledgements,
)

SOUND = b"\x01\x00" * 480
POOLS = (("Let me see.", "Good question."), ("Silent.",), ("Alright.", "Silent."))


def first(pool: Sequence[str]) -> str:
    return pool[0]


DRAW_FIRST: Draw = first


def kind(words: str) -> int | None:
    if words.endswith("?"):
        return 0
    return 1 if words.startswith("No") else None


async def voiced(sentence: str) -> bytes | None:
    return None if sentence.startswith("Silent") else SOUND


async def recorded() -> Clips:
    clips = Clips(kind=kind, draw=DRAW_FIRST)
    await record_acknowledgements(clips, voiced, POOLS)
    return clips


def test_no_clip_is_chosen_before_they_are_recorded() -> None:
    assert Clips(kind=kind, draw=DRAW_FIRST)("Where are we?") is None


@pytest.mark.anyio
async def test_the_kind_of_the_words_chooses_the_pool() -> None:
    assert (await recorded())("Where are we?") == ("Let me see.", SOUND)


@pytest.mark.anyio
async def test_words_of_no_kind_get_the_last_pool() -> None:
    assert (await recorded())("The repository is clean.") == ("Alright.", SOUND)


@pytest.mark.anyio
async def test_without_a_kind_every_words_get_the_last_pool() -> None:
    clips = Clips(draw=DRAW_FIRST)
    await record_acknowledgements(clips, voiced, POOLS)
    assert clips("Where are we?") == ("Alright.", SOUND)


@pytest.mark.anyio
async def test_a_kind_without_any_voiced_clip_plays_nothing() -> None:
    assert (await recorded())("No, it is fine.") is None


@pytest.mark.anyio
async def test_the_same_clip_is_not_played_twice_in_a_row() -> None:
    clips = await recorded()
    _ = clips("Where are we?")
    assert clips("And now?") == ("Good question.", SOUND)


@pytest.mark.anyio
async def test_a_sentence_without_voice_is_left_out() -> None:
    assert (await recorded()).pools[2] == {"Alright.": SOUND}
