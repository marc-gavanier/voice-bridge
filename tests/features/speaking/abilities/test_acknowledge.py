from collections.abc import Sequence

import pytest

from voice_bridge.features.speaking.abilities.acknowledge import (
    Acknowledgements,
    Clip,
    Clips,
    record_acknowledgements,
)

SOUND = b"\x01\x00" * 480
ACKNOWLEDGEMENTS = Acknowledgements(questions=("Voyons.",), statements=("D'accord.", "Silencieux."))


def first(pool: Sequence[Clip]) -> Clip:
    return pool[0]


async def voiced(sentence: str) -> bytes | None:
    return None if sentence.startswith("Silencieux") else SOUND


async def recorded() -> Clips:
    clips = Clips(choose=first)
    await record_acknowledgements(clips, voiced, ACKNOWLEDGEMENTS)
    return clips


def test_no_clip_is_chosen_before_they_are_recorded() -> None:
    assert Clips(choose=first)(question=True) is None


@pytest.mark.anyio
async def test_a_question_gets_a_question_clip() -> None:
    assert (await recorded())(question=True) == ("Voyons.", SOUND)


@pytest.mark.anyio
async def test_a_statement_gets_a_statement_clip() -> None:
    assert (await recorded())(question=False) == ("D'accord.", SOUND)


@pytest.mark.anyio
async def test_a_sentence_without_voice_is_left_out() -> None:
    assert (await recorded()).statements == (("D'accord.", SOUND),)
