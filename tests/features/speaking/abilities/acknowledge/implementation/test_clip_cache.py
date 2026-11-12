from dataclasses import dataclass, field
from pathlib import Path

import pytest

from voice_bridge.features.speaking.abilities.acknowledge.implementation.clip_cache import CachedVoice

pytestmark = pytest.mark.anyio

SOUND = b"\x01\x00" * 480


@dataclass
class Voice:
    asked: list[str] = field(default_factory=list)

    async def __call__(self, sentence: str) -> bytes | None:
        self.asked.append(sentence)
        return None if sentence.startswith("Silent") else SOUND


async def test_a_new_sentence_is_voiced(tmp_path: Path) -> None:
    assert await CachedVoice(voice=Voice(), directory=tmp_path, key="fr_female")("D'accord.") == SOUND


async def test_a_sentence_voiced_once_comes_from_the_cache(tmp_path: Path) -> None:
    voice = Voice()
    _ = await CachedVoice(voice=voice, directory=tmp_path, key="fr_female")("D'accord.")
    again = await CachedVoice(voice=voice, directory=tmp_path, key="fr_female")("D'accord.")
    assert (again, voice.asked) == (SOUND, ["D'accord."])


async def test_another_voice_does_not_reuse_the_cache(tmp_path: Path) -> None:
    voice = Voice()
    _ = await CachedVoice(voice=voice, directory=tmp_path, key="fr_female")("D'accord.")
    _ = await CachedVoice(voice=voice, directory=tmp_path, key="fr_male")("D'accord.")
    assert voice.asked == ["D'accord.", "D'accord."]


async def test_a_sentence_without_voice_is_not_cached(tmp_path: Path) -> None:
    voice = Voice()
    cached = CachedVoice(voice=voice, directory=tmp_path / "clips", key="fr_female")
    _ = await cached("Silent.")
    assert await cached("Silent.") is None
    assert voice.asked == ["Silent.", "Silent."]
