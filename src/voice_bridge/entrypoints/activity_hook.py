import sys

from voice_bridge.configuration.settings import load_settings
from voice_bridge.entrypoints.arguments import config_file
from voice_bridge.features.conversation.abilities.hold_conversation.implementation.claude_activity import (
    activity_of,
    tell_bridge,
)


def main() -> None:
    settings = load_settings(config_file("Tell the bridge whether Claude Code is working.", sys.argv[1:]))
    activity = activity_of(sys.stdin.read())
    if activity is not None:
        tell_bridge(settings.activity_socket, activity)
