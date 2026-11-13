import json

from voice_bridge.libraries.claude_code.hooks import ToolCall, denial, tool_call


def test_a_call_without_an_agent_is_the_main_agents() -> None:
    event = json.dumps({"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {}})
    assert tool_call(event) == ToolCall(tool="Bash", subagent=False)


def test_a_call_with_an_agent_is_a_subagents() -> None:
    event = json.dumps({"tool_name": "Bash", "agent_id": "a1b2", "agent_type": "general-purpose"})
    assert tool_call(event) == ToolCall(tool="Bash", subagent=True)


def test_a_call_without_a_tool_names_none() -> None:
    assert tool_call("{}") == ToolCall(tool="", subagent=False)


def test_a_denial_tells_claude_code_the_reason() -> None:
    assert json.loads(denial("Delegate.")) == {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": "Delegate.",
        }
    }
