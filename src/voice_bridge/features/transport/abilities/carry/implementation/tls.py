import ssl
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def pinned_context(certificate: Path) -> ssl.SSLContext:
    context = ssl.create_default_context(cafile=str(certificate))
    context.check_hostname = False
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    return context
