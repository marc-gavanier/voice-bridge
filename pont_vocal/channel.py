import json
import logging
import os
import re
import sys
import threading
from pathlib import Path

from pont_vocal.log import setup_log

SUPPORTED_PROTOCOLS = ["2025-06-18", "2025-03-26", "2024-11-05"]
log = logging.getLogger(__name__)
INSTRUCTIONS = (Path(__file__).resolve().parent.parent / "consignes-vocales.txt").read_text(encoding="utf-8").strip()
REPLY_TOOL = {
    "name": "reply",
    "description": "Dire une réponse à voix haute dans le casque de Marc",
    "_meta": {"anthropic/alwaysLoad": True},
    "inputSchema": {
        "type": "object",
        "properties": {"text": {"type": "string", "description": "Le texte à prononcer, rédigé pour l'oreille"}},
        "required": ["text"],
    },
}


def to_speech(text):
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"[*_`#]+", "", text)
    text = re.sub(r"^\s*[-–—]\s+", "", text, flags=re.M)
    return text.strip()


class ChannelServer:
    def __init__(self, send, on_reply):
        self.send = send
        self.on_reply = on_reply

    def handle(self, message):
        method = message.get("method")
        if "id" not in message:
            return None
        request_id = message["id"]
        if method == "initialize":
            return _result(request_id, self._initialize(message.get("params", {})))
        if method == "ping":
            return _result(request_id, {})
        if method == "tools/list":
            return _result(request_id, {"tools": [REPLY_TOOL]})
        if method == "tools/call":
            return _result(request_id, self._call_tool(message.get("params", {})))
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": f"Unknown method: {method}"}}

    def push(self, text, interrupted):
        meta = {"interrupted": "true"} if interrupted else {}
        self.send({"jsonrpc": "2.0", "method": "notifications/claude/channel", "params": {"content": text, "meta": meta}})

    def _initialize(self, params):
        requested = params.get("protocolVersion")
        return {
            "protocolVersion": requested if requested in SUPPORTED_PROTOCOLS else SUPPORTED_PROTOCOLS[0],
            "capabilities": {"experimental": {"claude/channel": {}}, "tools": {}},
            "serverInfo": {"name": "voix", "version": "0.1.0"},
            "instructions": INSTRUCTIONS,
        }

    def _call_tool(self, params):
        if params.get("name") != "reply":
            return {"isError": True, "content": [{"type": "text", "text": "unknown tool"}]}
        self.on_reply(params.get("arguments", {}).get("text", ""))
        return {"content": [{"type": "text", "text": "sent"}]}


def _result(request_id, result):
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def main():
    protocol_out = sys.stdout
    log_dir = Path(__file__).resolve().parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)
    sys.stdout = open(log_dir / "voix.log", "a", buffering=1, encoding="utf-8")
    setup_log(sys.stdout)
    write_lock = threading.Lock()

    def send(message):
        log.info(f"--> {json.dumps(message, ensure_ascii=False)[:600]}")
        with write_lock:
            protocol_out.write(json.dumps(message) + "\n")
            protocol_out.flush()

    from pont_vocal.bridge import VoiceBridge
    from pont_vocal.config import load_config
    from pont_vocal.transcription import Transcriber
    from pont_vocal.voice import VoxtralVoice

    holder = {}
    server = ChannelServer(send, lambda text: holder["bridge"].say(to_speech(text)))

    def start_bridge():
        config = load_config()
        voice = VoxtralVoice(config.voxtral_url, config.voxtral_voice, config.voice_gain)
        bridge = VoiceBridge(config, Transcriber(config.whisper_model), voice, on_text=server.push, name=os.environ.get("MUMBLE_NAME", "claude"))
        holder["bridge"] = bridge
        bridge.run()

    threading.Thread(target=start_bridge, daemon=True).start()
    for line in sys.stdin:
        if line.strip():
            log.info(f"<-- {line.strip()[:600]}")
            response = server.handle(json.loads(line))
            if response is not None:
                send(response)
    os._exit(0)


if __name__ == "__main__":
    main()
