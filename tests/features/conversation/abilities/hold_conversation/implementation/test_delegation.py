import json

from voice_bridge.features.conversation.abilities.hold_conversation.implementation.delegation import (
    delegation_answer,
)

MAIN_AGENT_TOOLS = frozenset({"mcp__voice__reply", "Agent"})


def main_agent_call(tool: str) -> str:
    return json.dumps({"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": {}})


def subagent_call(tool: str) -> str:
    return json.dumps({"hook_event_name": "PreToolUse", "tool_name": tool, "agent_id": "a1", "agent_type": "Explore"})


def test_a_working_tool_of_the_main_agent_is_denied_with_the_reason() -> None:
    answer = delegation_answer(main_agent_call("Bash"), allowed=MAIN_AGENT_TOOLS, reason="Delegate.")
    assert json.loads(answer or "{}")["hookSpecificOutput"]["permissionDecisionReason"] == "Delegate."


def test_an_allowed_tool_of_the_main_agent_runs() -> None:
    assert delegation_answer(main_agent_call("Agent"), allowed=MAIN_AGENT_TOOLS, reason="Delegate.") is None


def test_a_working_tool_of_a_subagent_runs() -> None:
    assert delegation_answer(subagent_call("Bash"), allowed=MAIN_AGENT_TOOLS, reason="Delegate.") is None
