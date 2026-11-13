from voice_bridge.features.conversation.domain.delegation import must_delegate
from voice_bridge.libraries.claude_code.hooks import denial, tool_call


def delegation_answer(event: str, *, allowed: frozenset[str], reason: str) -> str | None:
    call = tool_call(event)
    if not must_delegate(call.tool, subagent=call.subagent, allowed=allowed):
        return None
    return denial(reason)
