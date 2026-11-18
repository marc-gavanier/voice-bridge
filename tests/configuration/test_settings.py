import json
from importlib.resources import files
from pathlib import Path

import pytest
from platformdirs import user_state_path
from pydantic import ValidationError

from voice_bridge.configuration.settings import (
    LANGUAGES,
    ClaudeCodeSettings,
    FileSettings,
    FileSourceSettings,
    FolderSettings,
    FolderSourceSettings,
    OnnxEncoderSettings,
    OpenAISpeechSettings,
    SmartTurnEndOfTurnSettings,
    SmartTurnSettings,
    SpeechSynthesisSettings,
    VoiceActivitySettings,
    default_config_file,
    load_settings,
)

MINIMAL = """
[transport.mumble]
host = "voice.example.org"
password = "secret"
server_certificate = "/etc/voice-bridge/server.pem"
speaker_certificate_hash = "6f0b58787b96ff978ba512c74a1c3ca4aabab441"
"""

JSON_TRANSPORT = json.dumps(
    {
        "mumble": {
            "host": "env.example.org",
            "password": "p",
            "server_certificate": "/s.pem",
            "speaker_certificate_hash": "a",
        }
    }
)

SMART_TURN = (
    MINIMAL
    + """
[end_of_turn]
adapter = "smart_turn"
"""
)

HOLD_MUSIC_FILE = """
[hold_music.source]
adapter = "file"

[hold_music.source.file]
path = "/music/hold.mp3"
"""

HOLD_MUSIC_FOLDER = """
[hold_music.source]
adapter = "folder"

[hold_music.source.folder]
directories = ["/music"]
"""

EXAMPLE = Path(__file__).parents[2] / "config.example.toml"


@pytest.fixture
def config_file(tmp_path: Path) -> Path:
    path = tmp_path / "config.toml"
    _ = path.write_text(MINIMAL, encoding="utf-8")
    return path


def test_english_is_the_default_language(config_file: Path) -> None:
    assert load_settings(config_file).language == "en"


def test_the_mumble_server_comes_from_the_config_file(config_file: Path) -> None:
    assert load_settings(config_file).transport.mumble.host == "voice.example.org"


def test_the_standard_mumble_port_is_the_default(config_file: Path) -> None:
    assert load_settings(config_file).transport.mumble.port == 64738


def test_the_password_is_hidden_when_printed(config_file: Path) -> None:
    assert "secret" not in repr(load_settings(config_file))


def test_the_password_is_still_readable_on_purpose(config_file: Path) -> None:
    assert load_settings(config_file).transport.mumble.password.get_secret_value() == "secret"


def test_an_environment_variable_overrides_the_config_file(config_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VOICE_BRIDGE_LANGUAGE", "fr")
    assert load_settings(config_file).language == "fr"


def test_a_nested_environment_variable_overrides_the_config_file(
    config_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VOICE_BRIDGE_TRANSPORT__MUMBLE__HOST", "other.example.org")
    assert load_settings(config_file).transport.mumble.host == "other.example.org"


def test_an_adapters_secret_is_read_from_the_environment(config_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VOICE_BRIDGE_TRANSPORT__MUMBLE__PASSWORD", "from-the-environment")
    assert load_settings(config_file).transport.mumble.password.get_secret_value() == "from-the-environment"


def test_mumble_carries_the_voice_by_default(config_file: Path) -> None:
    assert load_settings(config_file).transport.adapter == "mumble"


def test_an_unknown_transport_stops_the_start(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    _ = path.write_text('[transport]\nadapter = "discord"\n' + MINIMAL, encoding="utf-8")
    with pytest.raises(ValidationError, match="adapter"):
        _ = load_settings(path)


def test_the_settings_of_an_adapter_not_chosen_stop_the_start(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    _ = path.write_text(MINIMAL + '[transport.discord]\ntoken = "secret"\n', encoding="utf-8")
    with pytest.raises(ValidationError, match="discord"):
        _ = load_settings(path)


def test_claude_code_is_the_assistant_by_default(config_file: Path) -> None:
    assert load_settings(config_file).assistant.adapter == "claude_code"


def test_no_claude_code_process_is_known_by_default(config_file: Path) -> None:
    assert load_settings(config_file).assistant.claude_code.claude_pid is None


def test_the_launcher_tells_the_claude_code_process(config_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VOICE_BRIDGE_ASSISTANT__CLAUDE_CODE__CLAUDE_PID", "4242")
    assert load_settings(config_file).assistant.claude_code.claude_pid == 4242


def test_the_stop_flag_belongs_to_claude_code(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    _ = path.write_text(MINIMAL + '[assistant.claude_code]\nstop_flag = "/run/stop"\n', encoding="utf-8")
    assert load_settings(path).assistant.claude_code.stop_flag == Path("/run/stop")


def test_the_activity_socket_belongs_to_claude_code(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    _ = path.write_text(MINIMAL + '[assistant.claude_code]\nactivity_socket = "/run/activity.sock"\n', encoding="utf-8")
    assert load_settings(path).assistant.claude_code.activity_socket == Path("/run/activity.sock")


def test_the_instructions_file_belongs_to_claude_code(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    _ = path.write_text(MINIMAL + '[assistant.claude_code]\ninstructions_file = "/etc/voice.md"\n', encoding="utf-8")
    assert load_settings(path).assistant.claude_code.instructions_file == Path("/etc/voice.md")


def test_an_unknown_key_stops_the_start(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    _ = path.write_text(MINIMAL + 'mystery = "value"\n', encoding="utf-8")
    with pytest.raises(ValidationError, match="mystery"):
        _ = load_settings(path)


def test_a_missing_server_stops_the_start(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    _ = path.write_text("", encoding="utf-8")
    with pytest.raises(ValidationError, match="transport"):
        _ = load_settings(path)


def test_a_missing_config_file_falls_back_to_the_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "VOICE_BRIDGE_TRANSPORT",
        JSON_TRANSPORT,
    )
    assert load_settings(tmp_path / "absent.toml").transport.mumble.host == "env.example.org"


def test_faster_whisper_recognizes_the_speech_by_default(config_file: Path) -> None:
    assert load_settings(config_file).speech_recognition.adapter == "faster_whisper"


def test_the_speech_recognition_model_comes_from_its_adapters_section(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    _ = path.write_text(MINIMAL + '[speech_recognition.faster_whisper]\nmodel = "large-v3"\n', encoding="utf-8")
    assert load_settings(path).speech_recognition.faster_whisper.model == "large-v3"


def test_an_openai_compatible_server_synthesizes_the_speech_by_default(config_file: Path) -> None:
    assert load_settings(config_file).speech_synthesis.adapter == "openai"


def test_the_voice_defaults_to_the_one_of_the_language(config_file: Path) -> None:
    assert load_settings(config_file).speech_synthesis.openai.voice is None


def test_the_speech_server_comes_from_its_adapters_section(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    _ = path.write_text(
        MINIMAL + '[speech_synthesis.openai]\nurl = "http://speech.example.org:8880"\n', encoding="utf-8"
    )
    assert str(load_settings(path).speech_synthesis.openai.url) == "http://speech.example.org:8880/"


def test_the_gain_is_neutral_by_default(config_file: Path) -> None:
    assert load_settings(config_file).speech_synthesis.gain == 1.0


def test_the_speech_keeps_its_natural_speed_by_default(config_file: Path) -> None:
    assert load_settings(config_file).speech_synthesis.speed == 1.0


def test_the_speed_of_the_speech_comes_from_the_config_file(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    _ = path.write_text(MINIMAL + "[speech_synthesis]\nspeed = 1.2\n", encoding="utf-8")
    assert load_settings(path).speech_synthesis.speed == 1.2


def test_a_speed_below_half_stops_the_start() -> None:
    with pytest.raises(ValidationError, match="speed"):
        _ = SpeechSynthesisSettings(speed=0.49)


def test_a_speed_above_double_stops_the_start() -> None:
    with pytest.raises(ValidationError, match="speed"):
        _ = SpeechSynthesisSettings(speed=2.01)


def test_the_extreme_speeds_are_accepted() -> None:
    assert (SpeechSynthesisSettings(speed=0.5).speed, SpeechSynthesisSettings(speed=2.0).speed) == (0.5, 2.0)


def test_the_speech_server_gets_five_seconds_to_accept_the_connection_by_default() -> None:
    assert OpenAISpeechSettings().connect_timeout == 5.0


def test_the_speech_server_gets_ten_seconds_to_send_the_first_audio_by_default() -> None:
    assert OpenAISpeechSettings().first_audio_timeout == 10.0


def test_the_timeouts_of_the_speech_server_come_from_its_adapters_section(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    _ = path.write_text(
        MINIMAL + "[speech_synthesis.openai]\ntimeout = 30.0\nconnect_timeout = 2.0\nfirst_audio_timeout = 4.0\n",
        encoding="utf-8",
    )
    openai = load_settings(path).speech_synthesis.openai
    assert (openai.timeout, openai.connect_timeout, openai.first_audio_timeout) == (30.0, 2.0, 4.0)


def test_a_timeout_of_zero_stops_the_start() -> None:
    with pytest.raises(ValidationError, match="timeout"):
        _ = OpenAISpeechSettings(timeout=0.0)


def test_a_connect_timeout_of_zero_stops_the_start() -> None:
    with pytest.raises(ValidationError, match="connect_timeout"):
        _ = OpenAISpeechSettings(connect_timeout=0.0)


def test_a_first_audio_timeout_of_zero_stops_the_start() -> None:
    with pytest.raises(ValidationError, match="first_audio_timeout"):
        _ = OpenAISpeechSettings(first_audio_timeout=0.0)


def test_a_connect_timeout_longer_than_the_timeout_stops_the_start() -> None:
    with pytest.raises(ValidationError, match="connect_timeout"):
        _ = OpenAISpeechSettings(timeout=3.0, connect_timeout=3.1, first_audio_timeout=3.0)


def test_a_first_audio_timeout_longer_than_the_timeout_stops_the_start() -> None:
    with pytest.raises(ValidationError, match="first_audio_timeout"):
        _ = OpenAISpeechSettings(timeout=3.0, connect_timeout=3.0, first_audio_timeout=3.1)


def test_timeouts_as_long_as_the_timeout_are_accepted() -> None:
    openai = OpenAISpeechSettings(timeout=3.0, connect_timeout=3.0, first_audio_timeout=3.0)
    assert (openai.connect_timeout, openai.first_audio_timeout) == (3.0, 3.0)


def test_opentelemetry_records_the_telemetry_by_default(config_file: Path) -> None:
    assert load_settings(config_file).telemetry.adapter == "opentelemetry"


def test_an_unknown_telemetry_adapter_stops_the_start(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    _ = path.write_text(MINIMAL + '[telemetry]\nadapter = "statsd"\n', encoding="utf-8")
    with pytest.raises(ValidationError, match="adapter"):
        _ = load_settings(path)


def test_the_telemetry_is_written_beside_the_log_by_default(config_file: Path) -> None:
    settings = load_settings(config_file)
    assert settings.telemetry.opentelemetry.directory == settings.log_file.parent.parent / "telemetry"


def test_the_log_keeps_thirty_days_by_default(config_file: Path) -> None:
    assert load_settings(config_file).log_retention == 30


def test_the_telemetry_keeps_thirty_days_by_default(config_file: Path) -> None:
    assert load_settings(config_file).telemetry.opentelemetry.retention == 30


def test_keeping_the_telemetry_forever_is_asked_in_words(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    _ = path.write_text(MINIMAL + '[telemetry.opentelemetry]\nretention = "forever"\n', encoding="utf-8")
    assert load_settings(path).telemetry.opentelemetry.retention == "forever"


def test_no_retention_of_zero_days_is_accepted(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    _ = path.write_text("log_retention = 0\n" + MINIMAL, encoding="utf-8")
    with pytest.raises(ValidationError, match="log_retention"):
        _ = load_settings(path)


def test_a_retention_is_read_from_the_environment(config_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VOICE_BRIDGE_TELEMETRY__OPENTELEMETRY__RETENTION", "90")
    assert load_settings(config_file).telemetry.opentelemetry.retention == 90


def test_the_example_config_file_starts_the_bridge() -> None:
    assert load_settings(EXAMPLE).transport.mumble.host == "voice.example.org"


def test_the_default_config_file_is_named_after_the_bridge() -> None:
    assert default_config_file().parts[-2:] == ("voice-bridge", "config.toml")


def test_a_shortest_voice_longer_than_the_barge_in_stops_the_start() -> None:
    with pytest.raises(ValidationError, match="shortest_voice"):
        _ = VoiceActivitySettings(shortest_voice=0.6, barge_in=0.5)


def test_a_shortest_voice_as_long_as_the_barge_in_is_accepted() -> None:
    assert VoiceActivitySettings(shortest_voice=0.5, barge_in=0.5).shortest_voice == 0.5


def test_silero_detects_the_voice_by_default(config_file: Path) -> None:
    assert load_settings(config_file).voice_activity.adapter == "silero"


def test_the_voice_thresholds_come_from_the_voice_activity_section(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    _ = path.write_text(MINIMAL + "[voice_activity]\nvolume_threshold = 800.0\n", encoding="utf-8")
    assert load_settings(path).voice_activity.volume_threshold == 800.0


def test_the_end_of_turn_model_is_off_by_default(config_file: Path) -> None:
    assert load_settings(config_file).end_of_turn.adapter == "silence"


def test_the_silence_ending_a_turn_comes_from_the_end_of_turn_section(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    _ = path.write_text(MINIMAL + "[end_of_turn]\nsilence = 1.0\n", encoding="utf-8")
    assert load_settings(path).end_of_turn.silence == 1.0


def test_smart_turn_is_chosen_as_the_end_of_turns_adapter(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    _ = path.write_text(MINIMAL + '[end_of_turn]\nadapter = "smart_turn"\n', encoding="utf-8")
    assert load_settings(path).end_of_turn == SmartTurnEndOfTurnSettings()


def test_smart_turns_settings_come_from_its_own_section(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    _ = path.write_text(SMART_TURN + "[end_of_turn.smart_turn]\nturn_threshold = 0.7\n", encoding="utf-8")
    assert load_settings(path).end_of_turn == SmartTurnEndOfTurnSettings(
        smart_turn=SmartTurnSettings(turn_threshold=0.7)
    )


def test_smart_turns_settings_without_smart_turn_chosen_stop_the_start(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    _ = path.write_text(MINIMAL + "[end_of_turn.smart_turn]\nturn_threshold = 0.7\n", encoding="utf-8")
    with pytest.raises(ValidationError, match="smart_turn"):
        _ = load_settings(path)


def test_an_unknown_end_of_turn_stops_the_start(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    _ = path.write_text(MINIMAL + '[end_of_turn]\nadapter = "vad"\n', encoding="utf-8")
    with pytest.raises(ValidationError, match="vad"):
        _ = load_settings(path)


def test_smart_turn_is_chosen_from_the_environment(config_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VOICE_BRIDGE_END_OF_TURN__ADAPTER", "smart_turn")
    assert load_settings(config_file).end_of_turn.adapter == "smart_turn"


def test_a_short_pause_as_long_as_the_silence_stops_the_start() -> None:
    with pytest.raises(ValidationError, match="short_pause"):
        _ = SmartTurnEndOfTurnSettings(smart_turn=SmartTurnSettings(short_pause=0.8), silence=0.8)


def test_a_short_pause_shorter_than_the_silence_is_accepted() -> None:
    settings = SmartTurnEndOfTurnSettings(smart_turn=SmartTurnSettings(short_pause=0.3), silence=0.8)
    assert settings.smart_turn.short_pause == 0.3


def test_an_unfinished_silence_no_longer_than_the_silence_stops_the_start() -> None:
    with pytest.raises(ValidationError, match="unfinished_silence"):
        _ = SmartTurnEndOfTurnSettings(smart_turn=SmartTurnSettings(unfinished_silence=0.8), silence=0.8)


def test_smart_turns_bounds_are_checked_against_the_silence_of_the_config_file(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    _ = path.write_text(SMART_TURN + "silence = 0.1\n", encoding="utf-8")
    with pytest.raises(ValidationError, match="short_pause"):
        _ = load_settings(path)


def test_no_hold_music_plays_by_default(config_file: Path) -> None:
    assert load_settings(config_file).hold_music.source is None


def test_the_hold_music_comes_from_a_file(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    _ = path.write_text(MINIMAL + HOLD_MUSIC_FILE, encoding="utf-8")
    assert load_settings(path).hold_music.source == FileSourceSettings(file=FileSettings(path=Path("/music/hold.mp3")))


def test_the_hold_music_comes_from_a_folder(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    _ = path.write_text(MINIMAL + HOLD_MUSIC_FOLDER, encoding="utf-8")
    assert load_settings(path).hold_music.source == FolderSourceSettings(
        folder=FolderSettings(directories=(Path("/music"),))
    )


def test_the_hold_musics_file_path_is_read_from_the_environment(
    config_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VOICE_BRIDGE_HOLD_MUSIC__SOURCE", '{"adapter": "file", "file": {"path": "/music/env.mp3"}}')
    assert load_settings(config_file).hold_music.source == FileSourceSettings(
        file=FileSettings(path=Path("/music/env.mp3"))
    )


def test_a_hold_music_source_without_its_adapter_stops_the_start(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    _ = path.write_text(MINIMAL + '[hold_music.source.file]\npath = "/music/hold.mp3"\n', encoding="utf-8")
    with pytest.raises(ValidationError, match="adapter"):
        _ = load_settings(path)


def test_a_folders_settings_beside_a_file_source_stop_the_start(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    _ = path.write_text(
        MINIMAL + HOLD_MUSIC_FILE + '[hold_music.source.folder]\ndirectories = ["/music"]\n', encoding="utf-8"
    )
    with pytest.raises(ValidationError, match="folder"):
        _ = load_settings(path)


def test_clips_are_played_from_the_state_directory_by_default(config_file: Path) -> None:
    assert load_settings(config_file).clips.source.folder.directories == (user_state_path("voice-bridge") / "clips",)


def test_the_clips_directories_come_from_the_folders_section(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    _ = path.write_text(
        MINIMAL + '[clips.source.folder]\ndirectories = ["/srv/clips", "/srv/music"]\n', encoding="utf-8"
    )
    assert load_settings(path).clips.source.folder.directories == (Path("/srv/clips"), Path("/srv/music"))


def test_a_clips_directory_under_the_home_directory_is_made_absolute(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    _ = path.write_text(MINIMAL + '[clips.source.folder]\ndirectories = ["~/Music", "~"]\n', encoding="utf-8")
    assert load_settings(path).clips.source.folder.directories == (Path.home() / "Music", Path.home())


def test_a_folder_needs_at_least_one_directory() -> None:
    with pytest.raises(ValidationError, match="directories"):
        _ = FolderSettings(directories=())


def test_clips_are_read_from_a_folder_only(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    _ = path.write_text(MINIMAL + '[clips.source]\nadapter = "file"\n', encoding="utf-8")
    with pytest.raises(ValidationError, match="folder"):
        _ = load_settings(path)


def test_the_former_clips_directory_says_what_replaced_it(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    _ = path.write_text(MINIMAL + '[clips]\ndirectory = "/srv/clips"\n', encoding="utf-8")
    with pytest.raises(ValidationError, match=r"clips\.directory became directories in \[clips\.source\.folder\]"):
        _ = load_settings(path)


def test_a_clip_plays_at_its_own_volume_by_default(config_file: Path) -> None:
    assert load_settings(config_file).clips.volume == 1.0


def test_the_former_clip_limits_say_that_a_clip_is_streamed(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    _ = path.write_text(MINIMAL + "[clips]\nlongest = 300.0\nlargest = 50000000\n", encoding="utf-8")
    with pytest.raises(ValidationError, match=r"largest is gone: .*; clips\.longest is gone: a clip is streamed"):
        _ = load_settings(path)


def test_the_speech_engine_is_checked_on_its_health_route_by_default(config_file: Path) -> None:
    assert load_settings(config_file).speech_synthesis.openai.health == "/health"


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
    claude_code = load_settings(config_file).assistant.claude_code
    assert (claude_code.model, claude_code.subagent_model) == (None, None)


def test_the_models_of_claude_code_come_from_the_config_file(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    _ = path.write_text(
        MINIMAL + '[assistant.claude_code]\nmodel = "sonnet"\nsubagent_model = "claude-opus-5-5"\n', encoding="utf-8"
    )
    claude_code = load_settings(path).assistant.claude_code
    assert (claude_code.model, claude_code.subagent_model) == ("sonnet", "claude-opus-5-5")


def test_claude_code_is_said_not_to_answer_after_ten_seconds_by_default(config_file: Path) -> None:
    assert load_settings(config_file).assistant.claude_code.unanswered_after == 10.0


def test_the_wait_for_claude_code_to_answer_must_be_positive() -> None:
    with pytest.raises(ValidationError, match="unanswered_after"):
        _ = ClaudeCodeSettings(unanswered_after=0)


def test_a_model_with_a_longer_context_is_accepted() -> None:
    assert ClaudeCodeSettings(model="opus[1m]").model == "opus[1m]"


def test_an_empty_model_stops_the_start() -> None:
    with pytest.raises(ValidationError, match="model"):
        _ = ClaudeCodeSettings(model="")


def test_a_model_that_could_be_read_as_an_option_stops_the_start() -> None:
    with pytest.raises(ValidationError, match="subagent_model"):
        _ = ClaudeCodeSettings(subagent_model="--dangerously-skip-permissions")


def test_an_onnx_encoder_routes_the_acknowledgements_by_default(config_file: Path) -> None:
    assert load_settings(config_file).understanding.adapter == "onnx"


def test_the_routing_model_defaults_to_multilingual_minilm_at_a_pinned_revision(config_file: Path) -> None:
    assert load_settings(config_file).understanding.onnx == OnnxEncoderSettings(
        model="Qdrant/paraphrase-multilingual-MiniLM-L12-v2-onnx-Q",
        revision="faf4aa4225822f3bc6376869cb1164e8e3feedd0",
    )


def test_the_routing_model_comes_from_its_adapters_section(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    _ = path.write_text(
        MINIMAL + '[understanding.onnx]\nmodel = "example/encoder-onnx"\nrevision = "main"\n', encoding="utf-8"
    )
    assert load_settings(path).understanding.onnx == OnnxEncoderSettings(model="example/encoder-onnx", revision="main")


def test_the_routing_threshold_stays_in_the_understanding_section(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    _ = path.write_text(MINIMAL + "[understanding]\nthreshold = 0.65\n", encoding="utf-8")
    assert load_settings(path).understanding.threshold == 0.65
