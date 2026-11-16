from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    from voice_bridge.features.conversation.domain.board import Task
    from voice_bridge.features.conversation.domain.turn_taking import Recording


@dataclass(frozen=True, slots=True, kw_only=True)
class Prompt:
    text: str
    interrupted: bool = False
    acknowledgement: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class AgentMessageChunk:
    text: str
    recording: Recording | None = None
    closing: bool = False


@dataclass(frozen=True, slots=True, kw_only=True)
class TurnStarted:
    pass


@dataclass(frozen=True, slots=True, kw_only=True)
class TurnEnded:
    working: bool = False
    agents: tuple[Task, ...] | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class ToolCall:
    tool_call_id: str
    title: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ToolCallUpdate:
    tool_call_id: str
    title: str
    at: datetime


@dataclass(frozen=True, slots=True, kw_only=True)
class ToolCallCompleted:
    tool_call_id: str
    content: str = ""
    agents: tuple[Task, ...] | None = None


type Activity = TurnStarted | TurnEnded | ToolCall | ToolCallUpdate | ToolCallCompleted
type SessionUpdate = AgentMessageChunk | Activity
