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


def clip_names(directory: Path) -> list[str]:
    return sorted(path.name for path in directory.iterdir())


async def cached_by_an_older_key(directory: Path) -> list[str]:
    _ = await CachedVoice(voice=Voice(), directory=directory, key="older")("D'accord.")
    return clip_names(directory)


async def test_pruning_removes_the_clips_this_run_did_not_ask_for(tmp_path: Path) -> None:
    older = await cached_by_an_older_key(tmp_path)
    cached = CachedVoice(voice=Voice(), directory=tmp_path, key="fr_female")
    _ = await cached("D'accord.")
    await cached.prune()
    assert set(older) & set(clip_names(tmp_path)) == set()


async def test_pruning_keeps_the_clips_this_run_asked_for(tmp_path: Path) -> None:
    _ = await CachedVoice(voice=Voice(), directory=tmp_path, key="fr_female")("D'accord.")
    cached = CachedVoice(voice=Voice(), directory=tmp_path, key="fr_female")
    _ = await cached("D'accord.")
    _ = await cached("Je regarde.")
    await cached.prune()
    assert len(clip_names(tmp_path)) == 2


async def test_pruning_keeps_files_the_cache_did_not_write(tmp_path: Path) -> None:
    _ = (tmp_path / "notes.pcm").write_bytes(SOUND)
    cached = CachedVoice(voice=Voice(), directory=tmp_path, key="fr_female")
    await cached.prune()
    assert clip_names(tmp_path) == ["notes.pcm"]


async def test_pruning_a_cache_never_written_does_nothing(tmp_path: Path) -> None:
    await CachedVoice(voice=Voice(), directory=tmp_path / "clips", key="fr_female").prune()
    assert not (tmp_path / "clips").exists()
