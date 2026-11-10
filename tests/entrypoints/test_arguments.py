from pathlib import Path

from voice_bridge.configuration.settings import default_config_file
from voice_bridge.entrypoints.arguments import config_file


def test_the_config_file_is_in_the_user_configuration_directory_by_default() -> None:
    assert config_file("Bridge.", []) == default_config_file()


def test_the_config_file_can_be_given_on_the_command_line() -> None:
    assert config_file("Bridge.", ["--config", "/etc/voice-bridge.toml"]) == Path("/etc/voice-bridge.toml")
