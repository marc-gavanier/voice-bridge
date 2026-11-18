import secrets
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Final, NoReturn

from voice_bridge.features.speaking.domain.audio import Audio, AudioRefusedError
from voice_bridge.features.speaking.domain.shuffle import next_pass

if TYPE_CHECKING:
    from collections.abc import Callable

    from voice_bridge.features.speaking.domain.ports import Decoder

AUDIO_SUFFIXES: Final = (".aac", ".flac", ".m4a", ".mp3", ".ogg", ".opus", ".wav")


def _refuse(reason: str) -> NoReturn:
    raise AudioRefusedError(reason)


def _at_random(files: tuple[Path, ...], /) -> tuple[Path, ...]:
    return tuple(secrets.SystemRandom().sample(files, len(files)))


@dataclass(slots=True, kw_only=True)
class AudioFolder:
    directories: tuple[Path, ...]
    largest: int
    decode: Decoder
    rate: int
    draw: Callable[[tuple[Path, ...]], tuple[Path, ...]] = _at_random
    queue: tuple[Path, ...] = field(default=(), init=False)
    last: Path | None = field(default=None, init=False)

    def _listed(self) -> str:
        return ", ".join(str(directory) for directory in self.directories)

    def _inside(self, found: Path) -> bool:
        return any(found.is_relative_to(directory.resolve()) for directory in self.directories)

    def _allowed(self, asked: str) -> Path:
        path = Path(asked)
        if not path.is_absolute():
            _refuse(f"{asked} is not an absolute path")
        found = path.resolve()
        if not self._inside(found):
            _refuse(f"{asked} is outside {self._listed()}, where the audio must be")
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

    def _tracks(self) -> tuple[Path, ...]:
        found = sorted(
            path
            for directory in self.directories
            for path in directory.rglob("*")
            if path.suffix.lower() in AUDIO_SUFFIXES and path.is_file()
        )
        if not found:
            _refuse(f"{self._listed()} holds no audio file")
        return tuple(found)

    def pick(self) -> Audio:
        if not self.queue:
            self.queue = next_pass(self.draw(self._tracks()), last=self.last)
        self.last, *rest = self.queue
        self.queue = tuple(rest)
        return self._audio(self.last)
