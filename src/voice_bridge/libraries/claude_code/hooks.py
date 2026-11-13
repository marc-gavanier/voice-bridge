import json
from dataclasses import dataclass

from pydantic import BaseModel


@dataclass(frozen=True, slots=True, kw_only=True)
class ToolCall:
    tool: str
    subagent: bool


class _PreToolUse(BaseModel):
    tool_name: str = ""
    agent_id: str | None = None


def tool_call(event: str) -> ToolCall:
    hook = _PreToolUse.model_validate_json(event)
    return ToolCall(tool=hook.tool_name, subagent=hook.agent_id is not None)


def denial(reason: str) -> str:
    return json.dumps(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        }
    )
