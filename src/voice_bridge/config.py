import os
from dataclasses import dataclass
from pathlib import Path


def _load_env_file(path):
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


@dataclass(frozen=True)
class Config:
    mumble_host: str
    mumble_password: str
    voxtral_url: str
    voxtral_voice: str
    whisper_model: str
    voice_threshold: int
    voice_user: str
    voice_gain: float


def load_config():
    _load_env_file(Path(__file__).resolve().parents[2] / ".env")
    return Config(
        mumble_host=os.environ["MUMBLE_HOST"],
        mumble_password=os.environ["MUMBLE_PASSWORD"],
        voxtral_url=os.environ.get("VOXTRAL_URL", "http://127.0.0.1:8123"),
        voxtral_voice=os.environ.get("VOXTRAL_VOICE", "fr_female"),
        whisper_model=os.environ.get("WHISPER_MODEL", "large-v3-turbo"),
        voice_threshold=int(os.environ.get("VOICE_THRESHOLD", "500")),
        voice_user=os.environ.get("VOICE_USER", "marc"),
        voice_gain=float(os.environ.get("VOICE_GAIN", "2.5")),
    )
