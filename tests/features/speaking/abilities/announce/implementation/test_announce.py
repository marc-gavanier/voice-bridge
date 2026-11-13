import pytest

from voice_bridge.features.speaking.abilities.announce.domain.wording import Wording
from voice_bridge.features.speaking.abilities.announce.implementation.announce import (
    Announcements,
    record_announcements,
)

SOUND = b"\x01\x00" * 480
WORDING = Wording(
    at_work=("One at work.",),
    many_at_work="Silent many at work.",
    finished=("One finished, one left.",),
    many_left="One finished, many left.",
    none_at_work="None at work.",
)


async def voiced(sentence: str) -> bytes | None:
    return None if sentence.startswith("Silent") else SOUND


async def recorded() -> Announcements:
    announcements = Announcements(wording=WORDING)
    await record_announcements(announcements, voiced)
    return announcements


def test_no_announcement_is_ready_before_it_is_recorded() -> None:
    assert Announcements(wording=WORDING)(1, finished=False) is None


@pytest.mark.anyio
async def test_a_recorded_announcement_gives_its_sentence_and_voice() -> None:
    announcements = await recorded()
    assert announcements(1, finished=True) == ("One finished, one left.", SOUND)


@pytest.mark.anyio
async def test_an_announcement_without_voice_is_not_played() -> None:
    announcements = await recorded()
    assert announcements(2, finished=False) is None


@pytest.mark.anyio
async def test_the_number_of_announcements_ready_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("INFO")
    _ = await recorded()
    assert "4 announcements ready" in caplog.text
