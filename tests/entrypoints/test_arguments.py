from pathlib import Path

import pytest

from voice_bridge.configuration.settings import (
    DEFAULT_ACTIVITY_SOCKET,
    DEFAULT_LOG_FILE,
    DEFAULT_STOP_FLAG,
    default_config_file,
)
from voice_bridge.entrypoints.arguments import (
    activity_hook_options,
    claude_settings_options,
    config_file,
    tool_hook_options,
)


def test_the_config_file_is_in_the_user_configuration_directory_by_default() -> None:
    assert config_file("Bridge.", []) == default_config_file()


def test_the_config_file_can_be_given_on_the_command_line() -> None:
    assert config_file("Bridge.", ["--config", "/etc/voice-bridge.toml"]) == Path("/etc/voice-bridge.toml")


def test_the_activity_hook_tells_the_default_socket_and_logs_to_the_default_file() -> None:
    assert vars(activity_hook_options([])) == {"socket": DEFAULT_ACTIVITY_SOCKET, "log_file": DEFAULT_LOG_FILE}


def test_the_activity_hook_takes_its_socket_and_log_file_on_the_command_line() -> None:
    options = activity_hook_options(["--socket", "/run/bridge.sock", "--log-file", "/var/log/bridge.log"])
    assert vars(options) == {"socket": Path("/run/bridge.sock"), "log_file": Path("/var/log/bridge.log")}


def test_the_tool_hook_reads_the_default_stop_flag_in_english_by_default() -> None:
    assert vars(tool_hook_options([])) == {
        "stop_flag": DEFAULT_STOP_FLAG,
        "language": "en",
        "log_file": DEFAULT_LOG_FILE,
    }


def test_the_tool_hook_takes_its_stop_flag_language_and_log_file_on_the_command_line() -> None:
    options = tool_hook_options(["--stop-flag", "/run/stop", "--language", "fr", "--log-file", "/var/log/bridge.log"])
    assert vars(options) == {
        "stop_flag": Path("/run/stop"),
        "language": "fr",
        "log_file": Path("/var/log/bridge.log"),
    }


def test_the_tool_hook_refuses_an_unknown_language() -> None:
    with pytest.raises(SystemExit):
        _ = tool_hook_options(["--language", "xx"])


def test_the_claude_settings_name_the_project_they_run_from() -> None:
    assert claude_settings_options(["--project", "/src/voice-bridge"]).project == Path("/src/voice-bridge")
