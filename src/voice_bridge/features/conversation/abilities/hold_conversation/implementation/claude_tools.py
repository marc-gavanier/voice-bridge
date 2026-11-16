from typing import TYPE_CHECKING, Final

from voice_bridge.features.conversation.domain.delegation import must_delegate
from voice_bridge.libraries.claude_code.hooks import denial, tool_call

if TYPE_CHECKING:
    from collections.abc import Callable


AFTER_A_STOP: Final = frozenset({"mcp__voice__reply", "TaskStop"})
MAIN_AGENT: Final = frozenset(
    {
        "mcp__voice__reply",
        "mcp__voice__end_session",
        "mcp__voice__board",
        "mcp__voice__play",
        "Agent",
        "SendMessage",
        "TaskStop",
        "ListAgents",
        "Read",
        "Grep",
        "Glob",
        "ToolSearch",
        "Skill",
        "Workflow",
        "ScheduleWakeup",
        "CronCreate",
        "CronList",
        "CronDelete",
        "TaskCreate",
        "TaskGet",
        "TaskList",
        "TaskUpdate",
        "TodoWrite",
    }
)


def tool_answer(event: str, *, refused: Callable[[str], bool], stop: str, delegation: str) -> str | None:
    call = tool_call(event)
    if refused(call.tool):
        return denial(stop)
    if must_delegate(call.tool, subagent=call.subagent, allowed=MAIN_AGENT):
        return denial(delegation)
    return None
