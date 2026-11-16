import tomllib
from importlib.resources import files
from typing import TYPE_CHECKING, ClassVar

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from pathlib import Path

    from voice_bridge.configuration.settings import Language


class _Strict(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)


class AcknowledgementRoute(_Strict):
    name: str
    examples: tuple[str, ...]
    sentences: tuple[str, ...]
    threshold: float | None = None
    stops: bool = False
    greets: bool = False
    answers: bool = False


class AgentAnnouncements(_Strict):
    at_work: tuple[str, ...]
    many_at_work: str


class LanguagePack(_Strict):
    code: str
    voice: str
    acknowledgements: tuple[AcknowledgementRoute, ...]
    neutral_acknowledgements: tuple[str, ...]
    neutral_question_acknowledgements: tuple[str, ...]
    announcements: AgentAnnouncements
    stop_refusal: str
    delegation_refusal: str
    unanswered: str
    reply_tool_description: str
    reply_text_description: str
    end_tool_description: str
    end_text_description: str
    board_tool_description: str
    play_tool_description: str
    play_path_description: str
    play_label_description: str
    hallucinations: frozenset[str]
    hallucination_prefixes: tuple[str, ...]
    instructions: str

    @property
    def greetings(self) -> tuple[str, ...]:
        return tuple(sentence for route in self.acknowledgements if route.greets for sentence in route.sentences)


def parse_language_pack(text: str, *, instructions: str) -> LanguagePack:
    return LanguagePack.model_validate({**tomllib.loads(text), "instructions": instructions})


def _packaged(language: Language, extension: str) -> str:
    return (
        files("voice_bridge.configuration").joinpath("languages", f"{language}.{extension}").read_text(encoding="utf-8")
    )


def language_pack(language: Language) -> LanguagePack:
    return parse_language_pack(_packaged(language, "toml"), instructions=_packaged(language, "md").strip())


def load_instructions(path: Path, default: str) -> str:
    return path.read_text(encoding="utf-8").strip() if path.exists() else default
