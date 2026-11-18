import tomllib
from pathlib import Path
from typing import Annotated, ClassVar, Literal, Self, cast, override

from platformdirs import user_cache_path, user_config_path, user_log_path, user_runtime_path, user_state_path
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    JsonValue,
    NonNegativeFloat,
    PositiveFloat,
    PositiveInt,
    SecretStr,
    model_validator,
)
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

APP_NAME = "voice-bridge"

type Language = Literal["ar", "de", "en", "es", "fr", "hi", "it", "nl", "pt"]

LANGUAGES: tuple[Language, ...] = ("ar", "de", "en", "es", "fr", "hi", "it", "nl", "pt")
DEFAULT_LANGUAGE: Language = "en"
DEFAULT_STOP_FLAG = user_runtime_path(APP_NAME) / "stop"
DEFAULT_LOG_FILE = user_log_path(APP_NAME) / f"{APP_NAME}.log"
DEFAULT_ACTIVITY_SOCKET = user_runtime_path(APP_NAME) / "activity.sock"

type Retention = PositiveInt | Literal["forever"]

type ClaudeModel = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9.-]*(\[1m\])?$")]


class Section(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)


class MumbleSettings(Section):
    host: str
    port: int = 64738
    password: SecretStr
    username: str = "claude"
    server_certificate: Path
    speaker_certificate_hash: str


class SpeechSettings(Section):
    url: HttpUrl = HttpUrl("http://127.0.0.1:8123")
    model: str = "mistralai/Voxtral-4B-TTS-2603"
    voice: str | None = None
    gain: float = 1.0
    speed: Annotated[float, Field(ge=0.5, le=2.0)] = 1.0
    timeout: float = 120.0
    health: str = "/health"


class WhisperSettings(Section):
    model: str = "large-v3-turbo"
    device: Literal["auto", "cuda", "cpu"] = "auto"
    compute_type: str = "default"


class HearingSettings(Section):
    volume_threshold: float = 500.0
    voice_probability: float = 0.5
    silence: float = 0.8
    longest: float = 30.0
    shortest_voice: float = 0.3
    preroll: float = 0.3
    barge_in: float = 0.5
    barge_window: float = 1.0
    smart_turn: bool = False
    short_pause: float = 0.2
    unfinished_silence: float = 2.0
    turn_threshold: float = 0.5
    settle: float = 1.2

    @model_validator(mode="after")
    def _an_interruption_is_never_dismissed(self) -> Self:
        if self.shortest_voice > self.barge_in:
            message = "shortest_voice must not exceed barge_in"
            raise ValueError(message)
        return self

    @model_validator(mode="after")
    def _a_short_pause_comes_before_the_silence(self) -> Self:
        if self.short_pause >= self.silence:
            message = "short_pause must be shorter than silence"
            raise ValueError(message)
        return self

    @model_validator(mode="after")
    def _an_unfinished_turn_waits_longer_than_the_silence(self) -> Self:
        if self.unfinished_silence <= self.silence:
            message = "unfinished_silence must be longer than silence"
            raise ValueError(message)
        return self


class HoldMusicSettings(Section):
    file: Path | None = None
    delay: float = 2.0
    volume: float = 0.3
    fade_in: NonNegativeFloat = 1.0
    fade_out: NonNegativeFloat = 0.3


def _keys_of(data: object) -> set[str]:
    return {str(key) for key in cast("dict[object, object]", data)} if isinstance(data, dict) else set()


REMOVED_CLIP_KEYS: dict[str, str] = {
    "directory": 'clips.directory became clips.directories, a list: directories = ["/path/to/clips"]',
    "largest": "clips.largest is gone: a clip is streamed, whatever its size",
    "longest": "clips.longest is gone: a clip is streamed, whatever its length",
}


class ClipsSettings(Section):
    directories: Annotated[tuple[Path, ...], Field(min_length=1)] = (user_state_path(APP_NAME) / "clips",)
    volume: NonNegativeFloat = 1.0

    @model_validator(mode="before")
    @classmethod
    def _removed_keys_say_what_replaced_them(cls, data: object) -> object:
        removed = sorted(REMOVED_CLIP_KEYS.keys() & _keys_of(data))
        if removed:
            raise ValueError("; ".join(REMOVED_CLIP_KEYS[key] for key in removed))
        return data


class ClaudeSettings(Section):
    model: ClaudeModel | None = None
    subagent_model: ClaudeModel | None = None
    unanswered_after: PositiveFloat = 10.0


class UnderstandingSettings(Section):
    model: str = "Qdrant/paraphrase-multilingual-MiniLM-L12-v2-onnx-Q"
    revision: str = "faf4aa4225822f3bc6376869cb1164e8e3feedd0"
    threshold: float = 0.6
    stop_flag: Path = DEFAULT_STOP_FLAG


class Settings(BaseSettings):
    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_prefix="VOICE_BRIDGE_", env_nested_delimiter="__", extra="forbid", frozen=True
    )

    language: Language = DEFAULT_LANGUAGE
    mumble: MumbleSettings
    speech: SpeechSettings = SpeechSettings()
    whisper: WhisperSettings = WhisperSettings()
    hearing: HearingSettings = HearingSettings()
    hold_music: HoldMusicSettings = HoldMusicSettings()
    clips: ClipsSettings = ClipsSettings()
    understanding: UnderstandingSettings = UnderstandingSettings()
    claude: ClaudeSettings = ClaudeSettings()
    instructions_file: Path = user_config_path(APP_NAME) / "instructions.md"
    log_file: Path = DEFAULT_LOG_FILE
    log_retention: Retention = 30
    logging: dict[str, JsonValue] | None = None
    telemetry_directory: Path = user_state_path(APP_NAME) / "telemetry"
    telemetry_retention: Retention = 30
    hang_after: PositiveFloat = 30.0
    activity_socket: Path = DEFAULT_ACTIVITY_SOCKET
    cache_directory: Path = user_cache_path(APP_NAME)
    claude_pid: int | None = None

    @classmethod
    @override
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (env_settings, init_settings)


def default_config_file() -> Path:
    return user_config_path(APP_NAME) / "config.toml"


def load_settings(config_file: Path) -> Settings:
    from_file = tomllib.loads(config_file.read_text(encoding="utf-8")) if config_file.exists() else {}
    return Settings.model_validate(from_file)
