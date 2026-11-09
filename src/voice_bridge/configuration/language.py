from dataclasses import dataclass
from importlib.resources import files
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from voice_bridge.configuration.settings import Language


@dataclass(frozen=True, slots=True, kw_only=True)
class LanguagePack:
    whisper_code: str
    voice: str
    greeting: str
    reply_tool_description: str
    reply_text_description: str
    hallucinations: frozenset[str]
    hallucination_prefixes: tuple[str, ...]
    instructions: str


def _packaged_instructions(language: Language) -> str:
    return (
        files("voice_bridge.configuration")
        .joinpath("instructions", f"{language}.md")
        .read_text(encoding="utf-8")
        .strip()
    )


def language_pack(language: Language) -> LanguagePack:
    match language:
        case "en":
            return LanguagePack(
                whisper_code="en",
                voice="neutral_female",
                greeting="I'm listening.",
                reply_tool_description="Speak a reply aloud in the user's headset",
                reply_text_description="The text to speak, written for the ear",
                hallucinations=frozenset({"", "you", "thank you", "thanks for watching"}),
                hallucination_prefixes=("subtitles by",),
                instructions=_packaged_instructions(language),
            )
        case "fr":
            return LanguagePack(
                whisper_code="fr",
                voice="fr_female",
                greeting="Je t'écoute.",
                reply_tool_description="Dire une réponse à voix haute dans le casque de l'utilisateur",
                reply_text_description="Le texte à prononcer, rédigé pour l'oreille",
                hallucinations=frozenset({"", "merci", "je vous prie"}),
                hallucination_prefixes=("sous-titrage",),
                instructions=_packaged_instructions(language),
            )


def load_instructions(path: Path, default: str) -> str:
    return path.read_text(encoding="utf-8").strip() if path.exists() else default
