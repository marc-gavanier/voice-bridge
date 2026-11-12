import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from voice_bridge.features.speaking.abilities.acknowledge.domain.candidates import candidates

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Sequence

    from voice_bridge.features.speaking.abilities.acknowledge.domain.ports import Draw

logger = logging.getLogger(__name__)

type Clip = tuple[str, bytes]


def _no_kind(_words: str) -> int | None:
    return None


@dataclass(slots=True, kw_only=True)
class Clips:
    draw: Draw
    kind: Callable[[str], int | None] = field(default=_no_kind)
    pools: list[dict[str, bytes]] = field(default_factory=list)
    last: dict[int, str] = field(default_factory=dict)

    def __call__(self, words: str) -> Clip | None:
        found = candidates(self.pools, self.kind(words), self.last)
        if found is None:
            return None
        sentence = self.draw(found.sentences)
        self.last[found.pool] = sentence
        return sentence, self.pools[found.pool][sentence]


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
