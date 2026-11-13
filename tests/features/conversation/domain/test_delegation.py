from voice_bridge.features.conversation.domain.delegation import must_delegate

MAIN_AGENT_TOOLS = frozenset({"mcp__voice__reply", "Agent"})


def test_the_main_agent_must_delegate_a_working_tool() -> None:
    assert must_delegate("Bash", subagent=False, allowed=MAIN_AGENT_TOOLS)


def test_the_main_agent_keeps_its_allowed_tools() -> None:
    assert not must_delegate("Agent", subagent=False, allowed=MAIN_AGENT_TOOLS)


def test_a_subagent_keeps_every_tool() -> None:
    assert not must_delegate("Bash", subagent=True, allowed=MAIN_AGENT_TOOLS)
