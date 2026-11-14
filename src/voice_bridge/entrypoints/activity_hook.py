import logging
import sys
from datetime import datetime

from voice_bridge.entrypoints.arguments import activity_hook_options
from voice_bridge.entrypoints.logs import log_hook_to
from voice_bridge.features.conversation.abilities.hold_conversation.implementation.claude_activity import (
    news_of,
    tell_bridge,
)

logger = logging.getLogger(__name__)


def main() -> None:
    options = activity_hook_options(sys.argv[1:])
    log_hook_to(options.log_file)
    try:
        news = news_of(sys.stdin.read(), at=datetime.now().astimezone())
        if news is not None:
            tell_bridge(options.socket, news)
    except Exception:
        logger.exception("the activity hook failed")
        raise
