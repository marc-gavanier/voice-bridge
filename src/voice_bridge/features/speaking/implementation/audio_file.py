from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from voice_bridge.features.speaking.domain.audio import Audio, AudioRefusedError

if TYPE_CHECKING:
    from voice_bridge.features.speaking.domain.ports import Decoder


@dataclass(frozen=True, slots=True, kw_only=True)
class AudioFile:
    path: Path
    decode: Decoder
    rate: int

    def find(self, asked: str, /) -> Audio:
        if Path(asked) != self.path:
            message = f"{asked} is not {self.path}, the only file to play"
            raise AudioRefusedError(message)
        return self.pick()

    def pick(self) -> Audio:
        return Audio(name=self.path.name, frames=self.decode(str(self.path), self.rate))
