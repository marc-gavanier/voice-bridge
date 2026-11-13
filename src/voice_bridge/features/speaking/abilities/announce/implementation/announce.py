import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from voice_bridge.features.speaking.abilities.announce.domain.wording import Wording, every_sentence, sentence_for

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)


@dataclass(slots=True, kw_only=True)
class Announcements:
    wording: Wording
    clips: dict[str, bytes] = field(default_factory=dict)

    def __call__(self, at_work: int, *, finished: bool) -> tuple[str, bytes] | None:
        sentence = sentence_for(self.wording, at_work, finished=finished)
        pcm = self.clips.get(sentence)
        return None if pcm is None else (sentence, pcm)


async def record_announcements(announcements: Announcements, voice: Callable[[str], Awaitable[bytes | None]]) -> None:
    clips: dict[str, bytes] = {}
    for sentence in every_sentence(announcements.wording):
        pcm = await voice(sentence)
        if pcm is not None:
            clips[sentence] = pcm
    announcements.clips = clips
    logger.info("%d announcements ready", len(clips))
