import hashlib
import logging
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Final

import anyio

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from pathlib import Path

logger = logging.getLogger(__name__)

CLIP_NAME: Final = re.compile(r"[0-9a-f]{64}\.pcm")


@dataclass(frozen=True, slots=True, kw_only=True)
class CachedVoice:
    voice: Callable[[str], Awaitable[bytes | None]]
    directory: Path
    key: str
    asked: set[str] = field(default_factory=set)

    def _path(self, sentence: str) -> anyio.Path:
        digest = hashlib.sha256(f"{self.key}\n{sentence}".encode()).hexdigest()
        return anyio.Path(self.directory) / f"{digest}.pcm"

    async def __call__(self, sentence: str) -> bytes | None:
        path = self._path(sentence)
        self.asked.add(path.name)
        if await path.exists():
            return await path.read_bytes()
        pcm = await self.voice(sentence)
        if pcm is not None:
            await path.parent.mkdir(parents=True, exist_ok=True)
            _ = await path.write_bytes(pcm)
        return pcm

    async def prune(self) -> None:
        stale = [
            path
            async for path in anyio.Path(self.directory).glob("*.pcm")
            if CLIP_NAME.fullmatch(path.name) and path.name not in self.asked
        ]
        for path in stale:
            await path.unlink(missing_ok=True)
        if stale:
            logger.info("%d stale clips removed from %s", len(stale), self.directory)
