import logging
import sys
from typing import Final

from voice_bridge.configuration.language import language_pack
from voice_bridge.entrypoints.arguments import tool_hook_options
from voice_bridge.entrypoints.logs import log_hook_to
from voice_bridge.features.conversation.abilities.hold_conversation.implementation.delegation import (
    delegation_answer,
)
from voice_bridge.features.understanding.abilities.understand.implementation.understand import pre_tool_use_answer

logger = logging.getLogger(__name__)

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


def main() -> None:
    options = tool_hook_options(sys.argv[1:])
    log_hook_to(options.log_file)
    try:
        event = sys.stdin.read()
        pack = language_pack(options.language)
        answer = pre_tool_use_answer(
            event, stopped=options.stop_flag.exists(), allowed=AFTER_A_STOP, reason=pack.stop_refusal
        ) or delegation_answer(event, allowed=MAIN_AGENT, reason=pack.delegation_refusal)
        if answer is not None:
            _ = sys.stdout.write(answer)
    except Exception:
        logger.exception("the tool hook failed")
        raise
