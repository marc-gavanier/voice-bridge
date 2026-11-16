import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from voice_bridge.features.conversation.abilities.hold_conversation.domain.assistant import AgentMessageChunk

if TYPE_CHECKING:
    from anyio.abc import ObjectSendStream

    from voice_bridge.features.conversation.abilities.hold_conversation.domain.assistant import Prompt, SessionUpdate

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True, kw_only=True)
class Echo:
    updates: ObjectSendStream[SessionUpdate]

    async def prompt(self, prompt: Prompt) -> None:
        logger.info(
            "repeating %r%s, acknowledged with %r",
            prompt.text,
            " after an interruption" if prompt.interrupted else "",
            prompt.acknowledgement,
        )
        await self.updates.send(AgentMessageChunk(text=prompt.text))

    async def close(self) -> None:
        logger.info("the rehearsal has no assistant to end")
