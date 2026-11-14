import json
import shlex
import sys

from voice_bridge.configuration.settings import load_settings
from voice_bridge.entrypoints.arguments import claude_settings_options
from voice_bridge.libraries.claude_code.hooks import hook_settings


def main() -> None:
    options = claude_settings_options(sys.argv[1:])
    settings = load_settings(options.config)
    run = ["uv", "run", "--project", str(options.project), "--frozen", "--quiet"]
    log_file = ["--log-file", str(settings.log_file)]
    activity = [*run, "voice-bridge-activity-hook", "--socket", str(settings.activity_socket), *log_file]
    tool = [
        *run,
        "voice-bridge-tool-hook",
        "--stop-flag",
        str(settings.understanding.stop_flag),
        "--language",
        settings.language,
        *log_file,
    ]
    _ = sys.stdout.write(json.dumps(hook_settings(activity=shlex.join(activity), tool=shlex.join(tool))))
