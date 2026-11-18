from importlib.resources import files
from pathlib import Path

import pytest
from platformdirs import user_state_path
from pydantic import ValidationError

from voice_bridge.configuration.settings import (
    LANGUAGES,
    ClaudeSettings,
    ClipsSettings,
    HearingSettings,
    SpeechSettings,
    UnderstandingSettings,
    default_config_file,
    load_settings,
)

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


def test_no_claude_code_process_is_known_by_default(config_file: Path) -> None:
    assert load_settings(config_file).claude_pid is None


def test_the_launcher_tells_the_claude_code_process(config_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VOICE_BRIDGE_CLAUDE_PID", "4242")
    assert load_settings(config_file).claude_pid == 4242


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
    assert load_settings(config_file).speech.voice is None


def test_the_gain_is_neutral_by_default(config_file: Path) -> None:
    assert load_settings(config_file).speech.gain == 1.0


def test_the_speech_keeps_its_natural_speed_by_default(config_file: Path) -> None:
    assert load_settings(config_file).speech.speed == 1.0


def test_the_speed_of_the_speech_comes_from_the_config_file(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    _ = path.write_text(MINIMAL + "[speech]\nspeed = 1.2\n", encoding="utf-8")
    assert load_settings(path).speech.speed == 1.2


def test_a_speed_below_half_stops_the_start() -> None:
    with pytest.raises(ValidationError, match="speed"):
        _ = SpeechSettings(speed=0.49)


def test_a_speed_above_double_stops_the_start() -> None:
    with pytest.raises(ValidationError, match="speed"):
        _ = SpeechSettings(speed=2.01)


def test_the_extreme_speeds_are_accepted() -> None:
    assert (SpeechSettings(speed=0.5).speed, SpeechSettings(speed=2.0).speed) == (0.5, 2.0)


def test_the_telemetry_is_written_beside_the_log_by_default(config_file: Path) -> None:
    settings = load_settings(config_file)
    assert settings.telemetry_directory == settings.log_file.parent.parent / "telemetry"


def test_the_log_keeps_thirty_days_by_default(config_file: Path) -> None:
    assert load_settings(config_file).log_retention == 30


def test_the_telemetry_keeps_thirty_days_by_default(config_file: Path) -> None:
    assert load_settings(config_file).telemetry_retention == 30


def test_keeping_the_telemetry_forever_is_asked_in_words(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    _ = path.write_text('telemetry_retention = "forever"\n' + MINIMAL, encoding="utf-8")
    assert load_settings(path).telemetry_retention == "forever"


def test_no_retention_of_zero_days_is_accepted(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    _ = path.write_text("log_retention = 0\n" + MINIMAL, encoding="utf-8")
    with pytest.raises(ValidationError, match="log_retention"):
        _ = load_settings(path)


def test_a_retention_is_read_from_the_environment(config_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VOICE_BRIDGE_TELEMETRY_RETENTION", "90")
    assert load_settings(config_file).telemetry_retention == 90


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


def test_clips_are_played_from_the_state_directory_by_default(config_file: Path) -> None:
    assert load_settings(config_file).clips.directories == (user_state_path("voice-bridge") / "clips",)


def test_the_clips_directories_come_from_the_config_file(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    _ = path.write_text(MINIMAL + '[clips]\ndirectories = ["/srv/clips", "/srv/music"]\n', encoding="utf-8")
    assert load_settings(path).clips.directories == (Path("/srv/clips"), Path("/srv/music"))


def test_a_clips_directory_under_the_home_directory_is_made_absolute(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    _ = path.write_text(MINIMAL + '[clips]\ndirectories = ["~/Music", "~"]\n', encoding="utf-8")
    assert load_settings(path).clips.directories == (Path.home() / "Music", Path.home())


def test_clips_need_at_least_one_directory() -> None:
    with pytest.raises(ValidationError, match="directories"):
        _ = ClipsSettings(directories=())


def test_the_former_clips_directory_says_what_replaced_it(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    _ = path.write_text(MINIMAL + '[clips]\ndirectory = "/srv/clips"\n', encoding="utf-8")
    with pytest.raises(ValidationError, match=r"clips\.directory became clips\.directories, a list"):
        _ = load_settings(path)


def test_a_clip_plays_at_its_own_volume_by_default(config_file: Path) -> None:
    assert load_settings(config_file).clips.volume == 1.0


def test_the_former_clip_limits_say_that_a_clip_is_streamed(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    _ = path.write_text(MINIMAL + "[clips]\nlongest = 300.0\nlargest = 50000000\n", encoding="utf-8")
    with pytest.raises(ValidationError, match=r"largest is gone: .*; clips\.longest is gone: a clip is streamed"):
        _ = load_settings(path)


def test_the_speech_engine_is_checked_on_its_health_route_by_default(config_file: Path) -> None:
    assert load_settings(config_file).speech.health == "/health"


def test_no_logging_section_is_set_by_default(config_file: Path) -> None:
    assert load_settings(config_file).logging is None


def test_the_logging_section_comes_from_the_config_file(config_file: Path) -> None:
    _ = config_file.write_text(f'{MINIMAL}\n[logging.loggers.httpx]\nlevel = "WARNING"\n', encoding="utf-8")
    assert load_settings(config_file).logging == {"loggers": {"httpx": {"level": "WARNING"}}}


def test_a_hang_is_reported_after_thirty_seconds_by_default(config_file: Path) -> None:
    assert load_settings(config_file).hang_after == 30.0


def test_a_hang_delay_must_be_positive(config_file: Path) -> None:
    _ = config_file.write_text(f"hang_after = 0\n{MINIMAL}", encoding="utf-8")
    with pytest.raises(ValidationError, match="hang_after"):
        _ = load_settings(config_file)


def language_files() -> list[str]:
    folder = files("voice_bridge.configuration") / "languages"
    return sorted(Path(entry.name).stem for entry in folder.iterdir() if entry.name.endswith(".toml"))


def test_every_language_shipped_can_be_chosen_for_the_hooks() -> None:
    assert language_files() == list(LANGUAGES)


def test_claude_code_chooses_its_own_models_by_default(config_file: Path) -> None:
    assert load_settings(config_file).claude == ClaudeSettings(model=None, subagent_model=None)


def test_the_models_of_claude_code_come_from_the_config_file(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    _ = path.write_text(MINIMAL + '[claude]\nmodel = "sonnet"\nsubagent_model = "claude-opus-5-5"\n', encoding="utf-8")
    assert load_settings(path).claude == ClaudeSettings(model="sonnet", subagent_model="claude-opus-5-5")


def test_claude_code_is_said_not_to_answer_after_ten_seconds_by_default(config_file: Path) -> None:
    assert load_settings(config_file).claude.unanswered_after == 10.0


def test_the_wait_for_claude_code_to_answer_must_be_positive() -> None:
    with pytest.raises(ValidationError, match="unanswered_after"):
        _ = ClaudeSettings(unanswered_after=0)


def test_a_model_with_a_longer_context_is_accepted() -> None:
    assert ClaudeSettings(model="opus[1m]").model == "opus[1m]"


def test_an_empty_model_stops_the_start() -> None:
    with pytest.raises(ValidationError, match="model"):
        _ = ClaudeSettings(model="")


def test_a_model_that_could_be_read_as_an_option_stops_the_start() -> None:
    with pytest.raises(ValidationError, match="subagent_model"):
        _ = ClaudeSettings(subagent_model="--dangerously-skip-permissions")


def test_the_routing_model_defaults_to_multilingual_minilm_at_a_pinned_revision(config_file: Path) -> None:
    assert load_settings(config_file).understanding == UnderstandingSettings(
        model="Qdrant/paraphrase-multilingual-MiniLM-L12-v2-onnx-Q",
        revision="faf4aa4225822f3bc6376869cb1164e8e3feedd0",
    )


def test_the_routing_model_comes_from_the_config_file(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    _ = path.write_text(
        MINIMAL + '[understanding]\nmodel = "example/encoder-onnx"\nrevision = "main"\n', encoding="utf-8"
    )
    understanding = load_settings(path).understanding
    assert (understanding.model, understanding.revision) == ("example/encoder-onnx", "main")
