import hashlib
from dataclasses import dataclass
from typing import TYPE_CHECKING

import anyio

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from pathlib import Path


@dataclass(frozen=True, slots=True, kw_only=True)
class CachedVoice:
    voice: Callable[[str], Awaitable[bytes | None]]
    directory: Path
    key: str

    def _path(self, sentence: str) -> anyio.Path:
        digest = hashlib.sha256(f"{self.key}\n{sentence}".encode()).hexdigest()
        return anyio.Path(self.directory) / f"{digest}.pcm"

    async def __call__(self, sentence: str) -> bytes | None:
        path = self._path(sentence)
        if await path.exists():
            return await path.read_bytes()
        pcm = await self.voice(sentence)
        if pcm is not None:
            await path.parent.mkdir(parents=True, exist_ok=True)
            _ = await path.write_bytes(pcm)
        return pcm
