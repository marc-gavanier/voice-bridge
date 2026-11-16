from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final, NoReturn

from voice_bridge.features.speaking.domain.audio import Audio, AudioRefusedError

if TYPE_CHECKING:
    from voice_bridge.features.speaking.domain.ports import Decoder

AUDIO_SUFFIXES: Final = (".aac", ".flac", ".m4a", ".mp3", ".ogg", ".opus", ".wav")


def _refuse(reason: str) -> NoReturn:
    raise AudioRefusedError(reason)


@dataclass(frozen=True, slots=True, kw_only=True)
class AudioFolder:
    directory: Path
    largest: int
    decode: Decoder
    rate: int

    def _allowed(self, asked: str) -> Path:
        path = Path(asked)
        if not path.is_absolute():
            _refuse(f"{asked} is not an absolute path")
        found = path.resolve()
        if not found.is_relative_to(self.directory.resolve()):
            _refuse(f"{asked} is outside {self.directory}, where the audio must be")
        if found.suffix.lower() not in AUDIO_SUFFIXES:
            _refuse(f"{asked} is not an audio file: its name must end with {', '.join(AUDIO_SUFFIXES)}")
        if not found.is_file():
            _refuse(f"{asked} is not a file")
        if found.stat().st_size > self.largest:
            _refuse(f"{asked} weighs over {self.largest} bytes")
        return found

    def _audio(self, path: Path) -> Audio:
        return Audio(name=path.name, frames=self.decode(str(path), self.rate))

    def find(self, asked: str, /) -> Audio:
        return self._audio(self._allowed(asked))
