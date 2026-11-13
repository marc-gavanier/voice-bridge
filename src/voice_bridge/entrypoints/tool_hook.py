import sys
from typing import Final

from voice_bridge.configuration.language import language_pack
from voice_bridge.configuration.settings import load_settings
from voice_bridge.entrypoints.arguments import config_file
from voice_bridge.features.conversation.abilities.hold_conversation.implementation.delegation import (
    delegation_answer,
)
from voice_bridge.features.understanding.abilities.understand.implementation.understand import pre_tool_use_answer

AFTER_A_STOP: Final = frozenset({"mcp__voice__reply", "TaskStop"})
MAIN_AGENT: Final = frozenset(
    {
        "mcp__voice__reply",
        "mcp__voice__end_session",
        "Agent",
        "SendMessage",
        "TaskStop",
        "ListAgents",
        "Read",
        "Grep",
        "Glob",
        "ToolSearch",
    }
)


def main() -> None:
    settings = load_settings(
        config_file("Refuse Claude Code's tools after a stop, and the main agent's working tools.", sys.argv[1:])
    )
    event = sys.stdin.read()
    pack = language_pack(settings.language)
    answer = pre_tool_use_answer(
        event, stopped=settings.understanding.stop_flag.exists(), allowed=AFTER_A_STOP, reason=pack.stop_refusal
    ) or delegation_answer(event, allowed=MAIN_AGENT, reason=pack.delegation_refusal)
    if answer is not None:
        _ = sys.stdout.write(answer)
