from pont_vocal.bridge import VoiceBridge
from pont_vocal.config import load_config
from pont_vocal.transcription import Transcriber
from pont_vocal.voice import VoxtralVoice


def main():
    config = load_config()
    transcriber = Transcriber(config.whisper_model)
    voice = VoxtralVoice(config.voxtral_url, config.voxtral_voice)
    bridge = VoiceBridge(config, transcriber, voice, on_text=lambda text, interrupted: bridge.say(text), name="relecture")
    bridge.run()


if __name__ == "__main__":
    main()
