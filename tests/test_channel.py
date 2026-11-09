from voice_bridge.channel import ChannelServer, to_speech


def make_server():
    sent = []
    replies = []
    server = ChannelServer(sent.append, replies.append)
    return server, sent, replies


def test_initialize_declares_channel_capability():
    server, _, _ = make_server()
    response = server.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}})
    capabilities = response["result"]["capabilities"]
    assert capabilities["experimental"]["claude/channel"] == {}
    assert capabilities["tools"] == {}
    assert response["result"]["instructions"]


def test_initialize_keeps_older_protocol_requested_by_client():
    server, _, _ = make_server()
    response = server.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26"}})
    assert response["result"]["protocolVersion"] == "2025-03-26"


def test_initialize_does_not_negotiate_unsupported_newer_protocol():
    server, _, _ = make_server()
    response = server.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2026-07-28"}})
    assert response["result"]["protocolVersion"] == "2025-06-18"


def test_notifications_get_no_response():
    server, _, _ = make_server()
    assert server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None


def test_tools_list_exposes_reply():
    server, _, _ = make_server()
    response = server.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    tool = response["result"]["tools"][0]
    assert tool["name"] == "reply"
    assert tool["inputSchema"]["required"] == ["text"]
    assert tool["_meta"]["anthropic/alwaysLoad"] is True


def test_reply_tool_forwards_text():
    server, _, replies = make_server()
    response = server.handle({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "reply", "arguments": {"text": "Bonjour Marc."}}})
    assert replies == ["Bonjour Marc."]
    assert response["result"]["content"][0]["text"] == "sent"


def test_unknown_tool_is_an_error():
    server, _, replies = make_server()
    response = server.handle({"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "other", "arguments": {}}})
    assert response["result"]["isError"] is True
    assert replies == []


def test_unknown_request_is_method_not_found():
    server, _, _ = make_server()
    response = server.handle({"jsonrpc": "2.0", "id": 5, "method": "resources/list"})
    assert response["error"]["code"] == -32601


def test_ping_answers_empty_result():
    server, _, _ = make_server()
    assert server.handle({"jsonrpc": "2.0", "id": 6, "method": "ping"})["result"] == {}


def test_push_sends_channel_notification():
    server, sent, _ = make_server()
    server.push("tu en es où", interrupted=False)
    assert sent[0]["method"] == "notifications/claude/channel"
    assert sent[0]["params"]["content"] == "tu en es où"
    assert "id" not in sent[0]


def test_push_flags_interruption():
    server, sent, _ = make_server()
    server.push("attends", interrupted=True)
    assert sent[0]["params"]["meta"]["interrupted"] == "true"


def test_to_speech_removes_markdown():
    assert to_speech("**Bon** `fichier.py` : voir [la doc](https://x.y)\n- point un") == "Bon fichier.py : voir la doc\npoint un"


def test_to_speech_drops_code_blocks():
    assert to_speech("Voici.\n```python\nprint(1)\n```\nFini.") == "Voici.\n\nFini."
