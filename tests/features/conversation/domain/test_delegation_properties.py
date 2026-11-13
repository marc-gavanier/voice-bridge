from hypothesis import given
from hypothesis import strategies as st

from voice_bridge.features.conversation.domain.delegation import must_delegate

TOOLS = st.text(max_size=12)
ALLOWED = st.frozensets(TOOLS, max_size=6)


@given(TOOLS, ALLOWED)
def test_a_subagent_never_has_to_delegate(tool: str, allowed: frozenset[str]) -> None:
    assert not must_delegate(tool, subagent=True, allowed=allowed)


@given(TOOLS, ALLOWED)
def test_the_main_agent_delegates_exactly_the_tools_it_is_not_allowed(tool: str, allowed: frozenset[str]) -> None:
    assert must_delegate(tool, subagent=False, allowed=allowed) == (tool not in allowed)
