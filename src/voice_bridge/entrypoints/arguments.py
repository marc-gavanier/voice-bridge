from argparse import ArgumentParser, Namespace
from pathlib import Path

from voice_bridge.configuration.settings import default_config_file


class Options(Namespace):
    def __init__(self) -> None:
        super().__init__()
        self.config: Path = default_config_file()


def config_file(description: str, arguments: list[str]) -> Path:
    parser = ArgumentParser(description=description)
    _ = parser.add_argument("--config", type=Path, help="the TOML settings file")
    return parser.parse_args(arguments, namespace=Options()).config
