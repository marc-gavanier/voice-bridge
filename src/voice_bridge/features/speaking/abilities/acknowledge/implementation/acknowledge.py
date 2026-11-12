import logging
import secrets
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from voice_bridge.features.speaking.domain.acknowledgement import fresh

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Sequence

logger = logging.getLogger(__name__)

type Clip = tuple[str, bytes]


def _no_kind(_words: str) -> int | None:
    return None


@dataclass(slots=True, kw_only=True)
class Clips:
    kind: Callable[[str], int | None] = field(default=_no_kind)
    pools: list[dict[str, bytes]] = field(default_factory=list)
    last: dict[int, str] = field(default_factory=dict)
    choose: Callable[[Sequence[str]], str] = field(default=secrets.choice)

    def __call__(self, words: str) -> Clip | None:
        if not self.pools:
            return None
        found = self.kind(words)
        kind = len(self.pools) - 1 if found is None else found
        pool = self.pools[kind]
        if not pool:
            return None
        sentence = self.choose(fresh(tuple(pool), self.last.get(kind)))
        self.last[kind] = sentence
        return sentence, pool[sentence]


async def _voiced(voice: Callable[[str], Awaitable[bytes | None]], sentences: Sequence[str]) -> dict[str, bytes]:
    clips: dict[str, bytes] = {}
    for sentence in sentences:
        pcm = await voice(sentence)
        if pcm is not None:
            clips[sentence] = pcm
    return clips


async def record_acknowledgements(
    clips: Clips, voice: Callable[[str], Awaitable[bytes | None]], pools: Sequence[Sequence[str]]
) -> None:
    recorded = [await _voiced(voice, sentences) for sentences in pools]
    clips.pools = recorded
    logger.info("%d acknowledgements ready", sum(len(pool) for pool in recorded))
