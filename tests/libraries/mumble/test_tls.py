import ssl
from pathlib import Path

from voice_bridge.libraries.mumble.tls import pinned_context

SERVER_CERTIFICATE = Path(__file__).parents[2] / "fixtures" / "server.pem"


def test_the_server_certificate_is_required() -> None:
    assert pinned_context(SERVER_CERTIFICATE).verify_mode == ssl.CERT_REQUIRED


def test_the_pinned_certificate_is_the_only_one_trusted() -> None:
    assert pinned_context(SERVER_CERTIFICATE).get_ca_certs()[0]["subject"] == ((("commonName", "Test Mumble Server"),),)


def test_the_host_name_is_not_checked_because_the_certificate_itself_is_pinned() -> None:
    assert not pinned_context(SERVER_CERTIFICATE).check_hostname


def test_protocols_older_than_tls_1_2_are_refused() -> None:
    assert pinned_context(SERVER_CERTIFICATE).minimum_version == ssl.TLSVersion.TLSv1_2
