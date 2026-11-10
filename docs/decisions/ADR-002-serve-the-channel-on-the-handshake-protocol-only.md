# ADR-002 — Serve the Claude channel on the MCP handshake protocol only

**Date**: 2026-11-10
**Status**: accepted — verified by voice with Claude Code 2.1.321 on 2026-11-10

## Context

The bridge is a [Claude Code channel](https://code.claude.com/docs/en/channels-reference): an MCP server that declares the experimental `claude/channel` capability and pushes `notifications/claude/channel` notifications into the session.

The rewrite moved from a hand-written JSON-RPC server to the official MCP SDK, version 2.3.0. That SDK serves two protocol generations and lets the client's first request choose one for the whole connection. Claude Code 2.1.321 opens with `server/discover` at protocol 2026-07-28, so the connection became a 2026-07-28 one, and the voice stopped reaching Claude in two steps:

1. The SDK's default `server/discover` handler recomputes the capabilities without the experimental ones, and Claude Code logged *Channel notifications skipped: server did not declare claude/channel capability*.
2. Once the capability was declared there too, Claude Code answered *this connection's protocol version has no channel delivery path*: it delivers channel messages only on the handshake protocols.

The hand-written server had worked because it answered `server/discover` with *Method not found*, and Claude Code fell back to the `initialize` handshake.

## Decision

Serve the channel with the SDK's `serve_loop`, which speaks the `initialize` handshake only, instead of `Server.run`. Claude Code's `server/discover` gets *Method not found*, Claude Code falls back to `initialize`, the connection settles on protocol 2025-11-25, and channel messages are delivered.

`serve_over_stdio` in `claude_channel.py` owns the transport and hands the conversation a function to forward to Claude. Its tests replay Claude Code's sequence over in-memory files: a modern discovery, refused, then the handshake declaring `claude/channel`, then a channel notification.

## Consequences

- The bridge depends on Claude Code falling back to the handshake when discovery is refused.
- Switching back to `Server.run`, or answering `server/discover`, breaks the voice silently: Claude Code then drops every message without an error. The tests on the refused discovery guard this.
- When Claude Code delivers channels on the 2026-07-28 protocol, this decision is to be revisited.

## Alternatives considered

- **Override `server/discover`** to declare the capability on the modern protocol, as the SDK's docstring offers. Tried first: necessary for the capability to be seen, not sufficient for messages to be delivered.
- **Keep the hand-written JSON-RPC server.** It worked, but stopped on a malformed line, crashed when a reply arrived before the bridge was ready, and hard-coded the protocol versions; the SDK validates messages and negotiates versions.
