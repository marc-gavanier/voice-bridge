from voice_bridge.libraries.claude_code.models import model_settings


def test_no_model_leaves_claude_codes_defaults() -> None:
    assert model_settings(model=None, subagent_model=None) == {}


def test_the_main_model_is_the_sessions_model_setting() -> None:
    assert model_settings(model="sonnet", subagent_model=None) == {"model": "sonnet"}


def test_the_subagent_model_is_claude_codes_subagent_variable() -> None:
    assert model_settings(model=None, subagent_model="opus") == {"env": {"CLAUDE_CODE_SUBAGENT_MODEL": "opus"}}


def test_both_models_are_set_together() -> None:
    assert model_settings(model="claude-sonnet-5-5", subagent_model="claude-opus-5-5") == {
        "model": "claude-sonnet-5-5",
        "env": {"CLAUDE_CODE_SUBAGENT_MODEL": "claude-opus-5-5"},
    }
