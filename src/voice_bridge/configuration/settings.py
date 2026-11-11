import tomllib
from pathlib import Path
from typing import ClassVar, Literal, Self, override

from platformdirs import user_cache_path, user_config_path, user_log_path
from pydantic import BaseModel, ConfigDict, HttpUrl, SecretStr, model_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

APP_NAME = "voice-bridge"

type Language = Literal["en", "fr"]


class Section(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)


class MumbleSettings(Section):
    host: str
    port: int = 64738
    password: SecretStr
    username: str = "claude"
    server_certificate: Path
    speaker_certificate_hash: str


class VoxtralSettings(Section):
    url: HttpUrl = HttpUrl("http://127.0.0.1:8123")
    model: str = "mistralai/Voxtral-4B-TTS-2603"
    voice: str | None = None
    gain: float = 1.0
    timeout: float = 120.0


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
    acknowledgement_delay: float = 0.5

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


class Settings(BaseSettings):
    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_prefix="VOICE_BRIDGE_", env_nested_delimiter="__", extra="forbid", frozen=True
    )

    language: Language = "en"
    mumble: MumbleSettings
    voxtral: VoxtralSettings = VoxtralSettings()
    whisper: WhisperSettings = WhisperSettings()
    hearing: HearingSettings = HearingSettings()
    hold_music: HoldMusicSettings = HoldMusicSettings()
    instructions_file: Path = user_config_path(APP_NAME) / "instructions.md"
    log_file: Path = user_log_path(APP_NAME) / f"{APP_NAME}.log"
    cache_directory: Path = user_cache_path(APP_NAME)

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
