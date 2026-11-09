from voice_bridge.bridge import VoiceBridge
from voice_bridge.config import load_config
from voice_bridge.transcription import Transcriber
from voice_bridge.voice import VoxtralVoice


def main():
    config = load_config()
    transcriber = Transcriber(config.whisper_model)
    voice = VoxtralVoice(config.voxtral_url, config.voxtral_voice, config.voice_gain)
    bridge = VoiceBridge(config, transcriber, voice, on_text=lambda text, interrupted: bridge.say(text), name="relecture")
    bridge.run()


if __name__ == "__main__":
    main()
