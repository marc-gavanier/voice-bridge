import json

from voice_bridge.libraries.claude_code.hooks import ToolCall, denial, hook_settings, tool_call

TURN_EVENTS = ("UserPromptSubmit", "Stop", "StopFailure", "SessionEnd")
ASYNC_ACTIVITY = [{"hooks": [{"type": "command", "command": "activity", "async": True}]}]
SYNC_ACTIVITY = [{"hooks": [{"type": "command", "command": "activity"}]}]


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


def test_the_settings_register_the_tool_hook_before_every_tool() -> None:
    assert hook_settings(activity="activity", tool="tool")["hooks"]["PreToolUse"][0]["matcher"] == "*"


def test_the_settings_wait_for_the_tool_hook_and_tell_each_tool_call_without_waiting() -> None:
    assert hook_settings(activity="activity", tool="tool")["hooks"]["PreToolUse"][0]["hooks"] == [
        {"type": "command", "command": "tool"},
        {"type": "command", "command": "activity", "async": True},
    ]


def test_the_settings_tell_turns_without_waiting_for_the_activity_hook() -> None:
    hooks = hook_settings(activity="activity", tool="tool")["hooks"]
    assert [hooks[event] for event in TURN_EVENTS] == [ASYNC_ACTIVITY] * 4


def test_the_settings_wait_for_the_activity_hook_on_agents_so_that_their_order_is_kept() -> None:
    hooks = hook_settings(activity="activity", tool="tool")["hooks"]
    assert [hooks["SubagentStart"], hooks["SubagentStop"]] == [SYNC_ACTIVITY] * 2
