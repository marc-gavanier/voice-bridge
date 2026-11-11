import logging
import re
import secrets
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from voice_bridge.features.speaking.domain.acknowledgement import fresh, kind_of

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Sequence

logger = logging.getLogger(__name__)

type Clip = tuple[str, bytes]
type AcknowledgementRule = tuple[str, tuple[str, ...]]


@dataclass(slots=True, kw_only=True)
class Clips:
    patterns: tuple[re.Pattern[str], ...] = ()
    pools: list[dict[str, bytes]] = field(default_factory=list)
    last: dict[int, str] = field(default_factory=dict)
    choose: Callable[[Sequence[str]], str] = field(default=secrets.choice)

    def __call__(self, words: str) -> Clip | None:
        kind = kind_of(words, self.patterns)
        if kind is None or not self.pools[kind]:
            return None
        pool = self.pools[kind]
        sentence = self.choose(fresh(tuple(pool), self.last.get(kind)))
        self.last[kind] = sentence
        return sentence, pool[sentence]


async def _voiced(voice: Callable[[str], Awaitable[bytes | None]], sentences: tuple[str, ...]) -> dict[str, bytes]:
    clips: dict[str, bytes] = {}
    for sentence in sentences:
        pcm = await voice(sentence)
        if pcm is not None:
            clips[sentence] = pcm
    return clips


async def record_acknowledgements(
    clips: Clips, voice: Callable[[str], Awaitable[bytes | None]], rules: Sequence[AcknowledgementRule]
) -> None:
    clips.patterns = tuple(re.compile(pattern, re.IGNORECASE) for pattern, _ in rules)
    clips.pools = [{} for _ in rules]
    for kind, (_, sentences) in enumerate(rules):
        clips.pools[kind] = await _voiced(voice, sentences)
    logger.info("%d acknowledgements ready", sum(len(pool) for pool in clips.pools))
