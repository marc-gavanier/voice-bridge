import logging
import sys
from functools import partial

from voice_bridge.configuration.language import language_pack
from voice_bridge.entrypoints.arguments import tool_hook_options
from voice_bridge.entrypoints.logs import log_hook_to
from voice_bridge.features.conversation.abilities.hold_conversation.implementation.claude_tools import (
    AFTER_A_STOP,
    tool_answer,
)
from voice_bridge.features.understanding.domain.meaning import refused

logger = logging.getLogger(__name__)


def main() -> None:
    options = tool_hook_options(sys.argv[1:])
    log_hook_to(options.log_file)
    try:
        event = sys.stdin.read()
        pack = language_pack(options.language)
        stopped = partial(refused, stopped=options.stop_flag.exists(), allowed=AFTER_A_STOP)
        answer = tool_answer(event, refused=stopped, stop=pack.stop_refusal, delegation=pack.delegation_refusal)
        if answer is not None:
            _ = sys.stdout.write(answer)
    except Exception:
        logger.exception("the tool hook failed")
        raise
