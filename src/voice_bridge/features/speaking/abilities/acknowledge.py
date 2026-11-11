import logging
import secrets
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Sequence

logger = logging.getLogger(__name__)

type Clip = tuple[str, bytes]


@dataclass(frozen=True, slots=True, kw_only=True)
class Acknowledgements:
    questions: tuple[str, ...]
    statements: tuple[str, ...]


@dataclass(slots=True, kw_only=True)
class Clips:
    questions: tuple[Clip, ...] = ()
    statements: tuple[Clip, ...] = ()
    choose: Callable[[Sequence[Clip]], Clip] = field(default=secrets.choice)

    def __call__(self, *, question: bool) -> Clip | None:
        pool = self.questions if question else self.statements
        return self.choose(pool) if pool else None


async def _voiced(voice: Callable[[str], Awaitable[bytes | None]], sentences: tuple[str, ...]) -> tuple[Clip, ...]:
    clips: list[Clip] = []
    for sentence in sentences:
        pcm = await voice(sentence)
        if pcm is not None:
            clips.append((sentence, pcm))
    return tuple(clips)


async def record_acknowledgements(
    clips: Clips, voice: Callable[[str], Awaitable[bytes | None]], acknowledgements: Acknowledgements
) -> None:
    clips.questions = await _voiced(voice, acknowledgements.questions)
    clips.statements = await _voiced(voice, acknowledgements.statements)
    logger.info("%d acknowledgements ready", len(clips.questions) + len(clips.statements))
