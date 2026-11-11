from pathlib import Path

import pytest
from pydantic import ValidationError

from voice_bridge.configuration.settings import HearingSettings, default_config_file, load_settings

MINIMAL = """
[mumble]
host = "voice.example.org"
password = "secret"
server_certificate = "/etc/voice-bridge/server.pem"
speaker_certificate_hash = "6f0b58787b96ff978ba512c74a1c3ca4aabab441"
"""


@pytest.fixture
def config_file(tmp_path: Path) -> Path:
    path = tmp_path / "config.toml"
    _ = path.write_text(MINIMAL, encoding="utf-8")
    return path


def test_english_is_the_default_language(config_file: Path) -> None:
    assert load_settings(config_file).language == "en"


def test_the_mumble_server_comes_from_the_config_file(config_file: Path) -> None:
    assert load_settings(config_file).mumble.host == "voice.example.org"


def test_the_standard_mumble_port_is_the_default(config_file: Path) -> None:
    assert load_settings(config_file).mumble.port == 64738


def test_the_password_is_hidden_when_printed(config_file: Path) -> None:
    assert "secret" not in repr(load_settings(config_file))


def test_the_password_is_still_readable_on_purpose(config_file: Path) -> None:
    assert load_settings(config_file).mumble.password.get_secret_value() == "secret"


def test_an_environment_variable_overrides_the_config_file(config_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VOICE_BRIDGE_LANGUAGE", "fr")
    assert load_settings(config_file).language == "fr"


def test_a_nested_environment_variable_overrides_the_config_file(
    config_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VOICE_BRIDGE_MUMBLE__HOST", "other.example.org")
    assert load_settings(config_file).mumble.host == "other.example.org"


def test_an_unknown_key_stops_the_start(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    _ = path.write_text(MINIMAL + 'mystery = "value"\n', encoding="utf-8")
    with pytest.raises(ValidationError, match="mystery"):
        _ = load_settings(path)


def test_a_missing_server_stops_the_start(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    _ = path.write_text("", encoding="utf-8")
    with pytest.raises(ValidationError, match="mumble"):
        _ = load_settings(path)


def test_a_missing_config_file_falls_back_to_the_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "VOICE_BRIDGE_MUMBLE",
        '{"host": "env.example.org", "password": "p", "server_certificate": "/s.pem", "speaker_certificate_hash": "a"}',
    )
    assert load_settings(tmp_path / "absent.toml").mumble.host == "env.example.org"


def test_the_voice_defaults_to_the_one_of_the_language(config_file: Path) -> None:
    assert load_settings(config_file).voxtral.voice is None


def test_the_gain_is_neutral_by_default(config_file: Path) -> None:
    assert load_settings(config_file).voxtral.gain == 1.0


def test_the_default_config_file_is_named_after_the_bridge() -> None:
    assert default_config_file().parts[-2:] == ("voice-bridge", "config.toml")


def test_a_shortest_voice_longer_than_the_barge_in_stops_the_start() -> None:
    with pytest.raises(ValidationError, match="shortest_voice"):
        _ = HearingSettings(shortest_voice=0.6, barge_in=0.5)


def test_a_shortest_voice_as_long_as_the_barge_in_is_accepted() -> None:
    assert HearingSettings(shortest_voice=0.5, barge_in=0.5).shortest_voice == 0.5


def test_a_barge_window_longer_than_the_silence_plus_the_barge_in_is_accepted() -> None:
    assert HearingSettings(silence=0.3, barge_in=0.5, barge_window=1.0).barge_window == 1.0


def test_the_end_of_turn_model_is_off_by_default() -> None:
    assert not HearingSettings().smart_turn


def test_a_short_pause_as_long_as_the_silence_stops_the_start() -> None:
    with pytest.raises(ValidationError, match="short_pause"):
        _ = HearingSettings(short_pause=0.8, silence=0.8)


def test_a_short_pause_shorter_than_the_silence_is_accepted() -> None:
    assert HearingSettings(short_pause=0.3, silence=0.8).short_pause == 0.3


def test_an_unfinished_silence_no_longer_than_the_silence_stops_the_start() -> None:
    with pytest.raises(ValidationError, match="unfinished_silence"):
        _ = HearingSettings(unfinished_silence=0.8, silence=0.8)


def test_no_hold_music_plays_by_default(config_file: Path) -> None:
    assert load_settings(config_file).hold_music.file is None


def test_the_hold_music_comes_from_the_config_file(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    _ = path.write_text(MINIMAL + '[hold_music]\nfile = "/music/hold.mp3"\n', encoding="utf-8")
    assert load_settings(path).hold_music.file == Path("/music/hold.mp3")
