import math
import sys
import time
from typing import TYPE_CHECKING, Final

import anyio

from voice_bridge.configuration.settings import Settings, load_settings
from voice_bridge.entrypoints.arguments import config_file
from voice_bridge.entrypoints.logs import configure_logging
from voice_bridge.entrypoints.voice import access
from voice_bridge.features.conversation.abilities.hold_conversation.implementation.telemetry import no_stall
from voice_bridge.features.recording.abilities.record.implementation.record import Recorder, record
from voice_bridge.libraries.mumble.audio import MUMBLE_RATE, Packet, named, pump_audio, with_pauses
from voice_bridge.libraries.mumble.connection import stay_connected

if TYPE_CHECKING:
    from pymumble_rev import MumbleClient

USERNAME: Final = "recorder"
PATIENCE: Final = 0.5


async def record_bridge(settings: Settings) -> None:
    packets_in, packets_out = anyio.create_memory_object_stream[Packet](math.inf)
    recorder = Recorder(directory=settings.log_file.parent / "recordings", rate=MUMBLE_RATE)

    async def connected(client: MumbleClient) -> None:
        await pump_audio(client, named(settings.mumble.username), packets_in, time.time, no_stall)

    async with packets_in, packets_out, anyio.create_task_group() as tasks:
        _ = tasks.start_soon(stay_connected, access(settings, USERNAME), connected)
        await record(recorder, with_pauses(packets_out, PATIENCE), time.time)


def main() -> None:
    settings = load_settings(config_file("Record the bridge's voice as it reaches Mumble.", sys.argv[1:]))
    configure_logging(settings.log_file.with_name("recorder.log"))
    anyio.run(record_bridge, settings)
