import logging
import socket
from typing import TYPE_CHECKING, Final, Literal

import anyio
from anyio.streams.buffered import BufferedByteReceiveStream
from pydantic import BaseModel, ValidationError

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from pathlib import Path

    from anyio.abc import SocketStream

logger = logging.getLogger(__name__)

type Activity = Literal["busy", "idle"]

LONGEST_LINE: Final = 16
SEND_TIMEOUT: Final = 1.0


class _HookEvent(BaseModel):
    hook_event_name: str = ""
    background_tasks: list[object] = []


def activity_of(event: str) -> Activity | None:
    try:
        hook = _HookEvent.model_validate_json(event)
    except ValidationError:
        return None
    match hook.hook_event_name:
        case "UserPromptSubmit":
            return "busy"
        case "Stop":
            return "busy" if hook.background_tasks else "idle"
        case "StopFailure" | "SessionEnd":
            return "idle"
        case _:
            return None


def tell_bridge(path: Path, activity: Activity) -> None:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(SEND_TIMEOUT)
        try:
            connection.connect(str(path))
            connection.sendall(f"{activity}\n".encode())
        except OSError:
            return


async def _read_activity(stream: SocketStream) -> Activity | None:
    async with stream:
        try:
            line = await BufferedByteReceiveStream(stream).receive_until(b"\n", LONGEST_LINE)
        except anyio.EndOfStream, anyio.IncompleteRead, anyio.DelimiterNotFound:
            return None
    match line:
        case b"busy":
            return "busy"
        case b"idle":
            return "idle"
        case _:
            return None


async def listen_to_claude(path: Path, heard: Callable[[Activity], Awaitable[None]]) -> None:
    await anyio.Path(path).parent.mkdir(parents=True, exist_ok=True)
    await anyio.Path(path).unlink(missing_ok=True)

    async def handle(stream: SocketStream) -> None:
        activity = await _read_activity(stream)
        if activity is None:
            return
        logger.info("Claude Code is %s", activity)
        await heard(activity)

    async with await anyio.create_unix_listener(path) as listener:
        await listener.serve(handle)
