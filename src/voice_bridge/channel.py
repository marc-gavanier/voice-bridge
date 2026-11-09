import json
import logging
import os
import re
import sys
import threading
from pathlib import Path

from voice_bridge.log import setup_log

SUPPORTED_PROTOCOLS = ["2025-06-18", "2025-03-26", "2024-11-05"]
log = logging.getLogger(__name__)
INSTRUCTIONS = (Path(__file__).resolve().parents[2] / "consignes-vocales.txt").read_text(encoding="utf-8").strip()
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

