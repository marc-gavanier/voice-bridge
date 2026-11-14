from argparse import ArgumentParser, Namespace
from pathlib import Path

from voice_bridge.configuration.settings import (
    DEFAULT_ACTIVITY_SOCKET,
    DEFAULT_LANGUAGE,
    DEFAULT_LOG_FILE,
    DEFAULT_STOP_FLAG,
    LANGUAGES,
    Language,
    default_config_file,
)


class Options(Namespace):
    def __init__(self) -> None:
        super().__init__()
        self.config: Path = default_config_file()


class ActivityHookOptions(Namespace):
    def __init__(self) -> None:
        super().__init__()
        self.socket: Path = DEFAULT_ACTIVITY_SOCKET
        self.log_file: Path = DEFAULT_LOG_FILE


class ToolHookOptions(Namespace):
    def __init__(self) -> None:
        super().__init__()
        self.stop_flag: Path = DEFAULT_STOP_FLAG
        self.language: Language = DEFAULT_LANGUAGE
        self.log_file: Path = DEFAULT_LOG_FILE


class ClaudeSettingsOptions(Options):
    def __init__(self) -> None:
        super().__init__()
        self.project: Path = Path()


def _parser(description: str) -> ArgumentParser:
    parser = ArgumentParser(description=description)
    _ = parser.add_argument("--log-file", type=Path, help="the bridge's log file, where a failure is written")
    return parser


def config_file(description: str, arguments: list[str]) -> Path:
    parser = ArgumentParser(description=description)
    _ = parser.add_argument("--config", type=Path, help="the TOML settings file")
    return parser.parse_args(arguments, namespace=Options()).config


def activity_hook_options(arguments: list[str]) -> ActivityHookOptions:
    parser = _parser("Tell the bridge what Claude Code and its agents do.")
    _ = parser.add_argument("--socket", type=Path, help="the bridge's activity socket")
    return parser.parse_args(arguments, namespace=ActivityHookOptions())


def tool_hook_options(arguments: list[str]) -> ToolHookOptions:
    parser = _parser("Refuse Claude Code's tools after a stop, and the main agent's working tools.")
    _ = parser.add_argument("--stop-flag", type=Path, help="the file whose presence refuses the tools")
    _ = parser.add_argument("--language", choices=LANGUAGES, help="the language of the refusals")
    return parser.parse_args(arguments, namespace=ToolHookOptions())


def claude_settings_options(arguments: list[str]) -> ClaudeSettingsOptions:
    parser = ArgumentParser(description="Print the Claude Code settings that register the bridge's hooks.")
    _ = parser.add_argument("--config", type=Path, help="the TOML settings file")
    _ = parser.add_argument("--project", type=Path, required=True, help="the checkout the hooks run from")
    return parser.parse_args(arguments, namespace=ClaudeSettingsOptions())
