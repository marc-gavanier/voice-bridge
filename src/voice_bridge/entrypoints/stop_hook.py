import sys
from typing import Final

from voice_bridge.configuration.language import language_pack
from voice_bridge.configuration.settings import load_settings
from voice_bridge.entrypoints.arguments import config_file
from voice_bridge.features.understanding.abilities.understand.implementation.understand import pre_tool_use_answer

ALLOWED: Final = frozenset({"mcp__voice__reply", "TaskStop"})


def main() -> None:
    settings = load_settings(config_file("Refuse Claude Code's tools after the speaker asked to stop.", sys.argv[1:]))
    answer = pre_tool_use_answer(
        sys.stdin.read(),
        stopped=settings.understanding.stop_flag.exists(),
        allowed=ALLOWED,
        reason=language_pack(settings.language).stop_refusal,
    )
    if answer is not None:
        _ = sys.stdout.write(answer)
