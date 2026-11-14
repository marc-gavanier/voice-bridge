import json
from dataclasses import dataclass
from typing import Final

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


TURN_EVENTS: Final = ("UserPromptSubmit", "Stop", "StopFailure", "SessionEnd")
AGENT_EVENTS: Final = ("SubagentStart", "SubagentStop")

type Command = dict[str, str | bool]
type Matcher = dict[str, str | list[Command]]


def _command(command: str, *, waited: bool) -> Command:
    run: Command = {"type": "command", "command": command}
    return run if waited else {**run, "async": True}


def hook_settings(*, activity: str, tool: str) -> dict[str, dict[str, list[Matcher]]]:
    return {
        "hooks": {
            "PreToolUse": [{"matcher": "*", "hooks": [_command(tool, waited=True), _command(activity, waited=False)]}],
            **{event: [{"hooks": [_command(activity, waited=False)]}] for event in TURN_EVENTS},
            **{event: [{"hooks": [_command(activity, waited=True)]}] for event in AGENT_EVENTS},
        }
    }
