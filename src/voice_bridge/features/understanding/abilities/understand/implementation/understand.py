import json
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from pydantic import BaseModel

from voice_bridge.features.understanding.domain.meaning import Meaning, Route, meaning_of, refused

if TYPE_CHECKING:
    from pathlib import Path

    from voice_bridge.features.understanding.abilities.understand.domain.ports import Scores

logger = logging.getLogger(__name__)


@dataclass(slots=True, kw_only=True)
class Understanding:
    scores: Scores
    routes: tuple[Route, ...]
    last: tuple[str, Meaning] | None = None

    def __call__(self, words: str) -> Meaning:
        if self.last is not None and self.last[0] == words:
            return self.last[1]
        meaning = meaning_of(self.scores(words.strip()), self.routes)
        name = "nothing" if meaning.route is None else self.routes[meaning.route].name
        logger.info("understood %r as %s (%.2f)", words, name, meaning.score)
        self.last = (words, meaning)
        return meaning


@dataclass(frozen=True, slots=True)
class StopFlag:
    path: Path

    def follow(self, meaning: Meaning) -> None:
        if meaning.stops:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.touch()
            logger.info("stop asked: tools refused until the next message")
        elif self.path.exists():
            self.path.unlink()
            logger.info("stop lifted by a new message")


class _ToolEvent(BaseModel):
    tool_name: str = ""


def pre_tool_use_answer(event: str, *, stopped: bool, allowed: frozenset[str], reason: str) -> str | None:
    if not refused(_ToolEvent.model_validate_json(event).tool_name, stopped=stopped, allowed=allowed):
        return None
    return json.dumps(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        }
    )
