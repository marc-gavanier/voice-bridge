from collections.abc import Awaitable, Callable, Iterator
from dataclasses import dataclass, field

import pytest
import stamina

from voice_bridge.features.speaking.abilities.speak.domain.ports import SynthesisError
from voice_bridge.features.speaking.abilities.speak.implementation.speak import (
    sentences_of,
    voice_of,
    voice_streamed,
    wait_until_ready,
)

SAMPLES = b"\x10\x00\xf0\xff"


def test_a_reply_becomes_sentences_written_for_the_ear() -> None:
    assert sentences_of("**Alright**, I am looking into it. See [the docs](https://x.y) right now.") == (
        "Alright, I am looking into it.",
        "See the docs right now.",
    )


@dataclass(frozen=True)
class Voiced:
    fingerprint: str = "voiced"

    async def whole(self, _sentence: str) -> bytes:
        return SAMPLES

    async def stream(self, _sentence: str, hear: Callable[[bytes], Awaitable[None]]) -> None:
        await hear(SAMPLES)

    async def ready(self) -> bool:
        return True


@dataclass(frozen=True)
class Voiceless:
    fingerprint: str = "voiceless"

    async def whole(self, sentence: str) -> bytes:
        raise SynthesisError(sentence)

    async def stream(self, sentence: str, _hear: Callable[[bytes], Awaitable[None]]) -> None:
        raise SynthesisError(sentence)

    async def ready(self) -> bool:
        return True


@dataclass(frozen=True)
class ReadyLater:
    answers: Iterator[bool]
    fingerprint: str = "ready later"

    async def whole(self, _sentence: str) -> bytes:
        return SAMPLES

    async def stream(self, _sentence: str, hear: Callable[[bytes], Awaitable[None]]) -> None:
        await hear(SAMPLES)

    async def ready(self) -> bool:
        return next(self.answers)


@dataclass
class Ear:
    heard: list[bytes] = field(default_factory=list)

    async def __call__(self, pcm: bytes) -> None:
        self.heard.append(pcm)


async def ignored(_pcm: bytes) -> None:
    pass


@pytest.mark.anyio
async def test_a_sentence_gets_the_whole_voice_of_the_synthesis() -> None:
    assert await voice_of(Voiced(), "Hello.") == SAMPLES


@pytest.mark.anyio
async def test_a_sentence_without_voice_is_skipped() -> None:
    assert await voice_of(Voiceless(), "Hello.") is None


@pytest.mark.anyio
async def test_a_streamed_sentence_is_heard_as_the_synthesis_streams_it() -> None:
    ear = Ear()
    _ = await voice_streamed(Voiced(), "Hello.", ear)
    assert ear.heard == [SAMPLES]


@pytest.mark.anyio
async def test_a_streamed_sentence_without_voice_tells_its_voice_failed() -> None:
    assert not await voice_streamed(Voiceless(), "Hello.", ignored)


@pytest.mark.anyio
async def test_a_streamed_sentence_without_voice_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    _ = await voice_streamed(Voiceless(), "Hello.", ignored)
    assert "no voice for 'Hello.'" in caplog.text


@pytest.mark.anyio
async def test_a_streamed_sentence_tells_its_voice_came_whole() -> None:
    assert await voice_streamed(Voiced(), "Hello.", ignored)


@pytest.mark.anyio
async def test_waiting_for_a_ready_synthesis_returns_at_once() -> None:
    assert await wait_until_ready(ReadyLater(answers=iter([True]))) is None


@pytest.mark.anyio
async def test_waiting_asks_again_until_the_synthesis_is_ready() -> None:
    with stamina.set_testing(True, attempts=2):
        assert await wait_until_ready(ReadyLater(answers=iter([False, True]))) is None
