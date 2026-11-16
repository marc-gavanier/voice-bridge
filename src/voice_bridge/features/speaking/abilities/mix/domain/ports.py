from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from voice_bridge.features.speaking.abilities.mix.domain.played import Played


class Reference(Protocol):
    def __call__(self, played: Played, /) -> None: ...
