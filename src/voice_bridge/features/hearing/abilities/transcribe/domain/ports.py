from typing import Protocol


class Report(Protocol):
    async def __call__(self, text: str, *, noise: bool) -> None: ...
