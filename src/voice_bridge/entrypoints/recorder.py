import math
import sys
import time
from functools import partial
from typing import Final

import anyio

from voice_bridge.configuration.settings import Settings, load_settings
from voice_bridge.entrypoints.arguments import config_file
from voice_bridge.entrypoints.crashes import crash_file_of, watching_crashes, watching_hangs
from voice_bridge.entrypoints.logs import configure_logging, run_logged
from voice_bridge.entrypoints.telemetry import report_errors
from voice_bridge.entrypoints.voice import access
from voice_bridge.features.recording.abilities.record.implementation.record import Recorder, record
from voice_bridge.features.transport.abilities.carry.domain.received import Frame
from voice_bridge.features.transport.abilities.carry.implementation.carry import carry, with_pauses
from voice_bridge.features.transport.abilities.carry.implementation.mumble import Mumble, named
from voice_bridge.features.transport.abilities.carry.implementation.mumble_connection import stay_connected

USERNAME: Final = "recorder"
PATIENCE: Final = 0.5


async def record_bridge(settings: Settings) -> None:
    frames_in, frames_out = anyio.create_memory_object_stream[Frame](math.inf)
    transport = Mumble(
        connection=partial(stay_connected, access(settings, USERNAME)),
        listened=named(settings.mumble.username),
        clock=time.time,
    )
    recorder = Recorder(directory=settings.log_file.parent / "recordings", rate=transport.rate)

    def unmeasured(_waited: float) -> None:
        return None

    async with frames_in, frames_out, anyio.create_task_group() as tasks:
        _ = tasks.start_soon(carry, transport, frames_in.send, unmeasured)
        await record(recorder, with_pauses(frames_out, PATIENCE), time.time)


def main() -> None:
    settings = load_settings(config_file("Record the bridge's voice as it reaches Mumble.", sys.argv[1:]))
    configure_logging(settings.log_file.with_name("recorder.log"), settings.log_retention)
    _ = report_errors()
    with watching_crashes(crash_file_of(settings.log_file.with_name("recorder.log"))) as watch:
        run_logged(watching_hangs, watch, settings.hang_after, partial(record_bridge, settings))
