import json

from voice_bridge.features.conversation.abilities.hold_conversation.implementation.claude_tools import (
    AFTER_A_STOP,
    MAIN_AGENT,
    tool_answer,
)


def main_agent_call(tool: str) -> str:
    return json.dumps({"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": {}})


def subagent_call(tool: str) -> str:
    return json.dumps({"hook_event_name": "PreToolUse", "tool_name": tool, "agent_id": "a1", "agent_type": "Explore"})


def stopped(tool: str) -> bool:
    return tool != "mcp__voice__reply"


def never_stopped(_tool: str) -> bool:
    return False


def answer_to(event: str, *, refused: bool = False) -> str | None:
    return tool_answer(event, refused=stopped if refused else never_stopped, stop="Stop.", delegation="Delegate.")


def test_a_tool_refused_after_a_stop_is_denied_with_the_reason() -> None:
    assert json.loads(answer_to(subagent_call("Bash"), refused=True) or "{}") == {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": "Stop.",
        }
    }


def test_the_stop_is_told_before_the_delegation() -> None:
    answer = answer_to(main_agent_call("Bash"), refused=True)
    assert json.loads(answer or "{}")["hookSpecificOutput"]["permissionDecisionReason"] == "Stop."


def test_a_tool_the_stop_allows_runs() -> None:
    assert answer_to(main_agent_call("mcp__voice__reply"), refused=True) is None


def test_a_working_tool_of_the_main_agent_is_denied_with_the_reason() -> None:
    answer = answer_to(main_agent_call("Bash"))
    assert json.loads(answer or "{}")["hookSpecificOutput"]["permissionDecisionReason"] == "Delegate."


def test_an_allowed_tool_of_the_main_agent_runs() -> None:
    assert answer_to(main_agent_call("Agent")) is None


def test_a_working_tool_of_a_subagent_runs() -> None:
    assert answer_to(subagent_call("Bash")) is None


def test_after_a_stop_only_the_reply_and_stopping_tasks_are_allowed() -> None:
    assert frozenset({"mcp__voice__reply", "TaskStop"}) == AFTER_A_STOP


def test_the_main_agent_keeps_the_channels_tools() -> None:
    assert {"mcp__voice__reply", "mcp__voice__end_session", "mcp__voice__board", "mcp__voice__play"} <= MAIN_AGENT


def test_the_main_agent_may_not_run_commands_or_edit_files() -> None:
    assert MAIN_AGENT.isdisjoint({"Bash", "Edit", "Write"})
