from dataclasses import dataclass


@dataclass(frozen=True, slots=True, kw_only=True)
class Voicing:
    volume_threshold: float
    probability: float


def is_voiced(voicing: Voicing, *, probability: float, volume: float) -> bool:
    return probability >= voicing.probability and volume >= voicing.volume_threshold
