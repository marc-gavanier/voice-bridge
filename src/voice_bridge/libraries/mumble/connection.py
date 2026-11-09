import ssl
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

import stamina
from pymumble_rev import ClientConfig, MumbleClient, MumbleError

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Awaitable, Callable
    from pathlib import Path

LONGEST_WAIT_BEFORE_RECONNECTING: Final = 30.0


class DisconnectedError(Exception):
    pass


@dataclass(frozen=True, slots=True, kw_only=True)
class Access:
    host: str
    port: int
    username: str
    password: str
    server_certificate: Path


def pinned_context(certificate: Path) -> ssl.SSLContext:
    context = ssl.create_default_context(cafile=str(certificate))
    context.check_hostname = False
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    return context


@asynccontextmanager
async def connected(access: Access) -> AsyncGenerator[MumbleClient]:
    config = ClientConfig(username=access.username, password=access.password, client_type="bot")
    client = MumbleClient(
        access.host,
        config,
        port=access.port,
        ssl_context=pinned_context(access.server_certificate),
        receive_audio=True,
    )
    async with client:
        yield client


async def stay_connected(access: Access, session: Callable[[MumbleClient], Awaitable[None]]) -> None:
    async for attempt in stamina.retry_context(
        on=(MumbleError, OSError, DisconnectedError),
        attempts=None,
        timeout=None,
        wait_max=LONGEST_WAIT_BEFORE_RECONNECTING,
    ):
        with attempt:
            async with connected(access) as client:
                await session(client)
                raise DisconnectedError(client.close_reason)
