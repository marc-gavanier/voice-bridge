import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True, kw_only=True)
class Hallucinations:
    texts: frozenset[str]
    prefixes: tuple[str, ...]


def _normalize(text: str) -> str:
    return " ".join(re.sub(r"[^\w\s'-]", " ", text.lower()).split()).strip("-\N{EN DASH} ")


def is_noise(text: str, hallucinations: Hallucinations) -> bool:
    normalized = _normalize(text)
    return normalized in hallucinations.texts or normalized.startswith(hallucinations.prefixes)
