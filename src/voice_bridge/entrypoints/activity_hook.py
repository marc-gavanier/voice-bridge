import sys

from voice_bridge.configuration.settings import load_settings
from voice_bridge.entrypoints.arguments import config_file
from voice_bridge.features.conversation.abilities.hold_conversation.implementation.claude_activity import (
    news_of,
    tell_bridge,
)


def main() -> None:
    settings = load_settings(config_file("Tell the bridge what Claude Code and its agents do.", sys.argv[1:]))
    news = news_of(sys.stdin.read())
    if news is not None:
        tell_bridge(settings.activity_socket, news)
