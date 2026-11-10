# ADR-001 — pymumble-rev as the Mumble client

**Date**: 2026-11-10
**Status**: accepted — tested against a Mumble 1.6.1001 server on 2026-11-10

## Context

The bridge first used pymumble 1.6.1, the client most Python Mumble bots descend from. Its last release dates from May 2021:

- It calls `ssl.wrap_socket`, removed in Python 3.12, so it held the project on Python 3.11.
- It pins `protobuf==3.12.2`, and through it `setuptools<81`: `uv audit` and pip-audit reported ten known vulnerabilities in the two.
- It opens TLS with `CERT_NONE` and falls back to TLS 1.0: it never verifies the server.

Upstream fixed the Python 3.12 issue in November 2023 but never published a release, and its maintainer is looking for someone to take it over, waiting for an official library from the Mumble project. That library, `mumble-voip/libmumble`, is C++ with no release and no Python binding. The maintained Python bots each vendor a patched copy of pymumble.

## Decision

Use **pymumble-rev**, pinned to an exact version, behind `voice_bridge.libraries.mumble`. It is the only Python client that is released, asynchronous and typed, runs on Python 3.12 to 3.14, takes an `SSLContext`, exposes each user's certificate hash, keeps the server state immutable and calls the system libopus directly, without protobuf 3.

It was checked against the Mumble server the bridge uses, version 1.6.1001, before adopting it: the connection with the server's certificate pinned succeeds, another certificate is refused before the password is sent, the phone's certificate hash reaches the bridge, and audio arrives split by session.

## Consequences

- Python 3.14, no known vulnerability in the dependencies, and a verified server.
- pymumble-rev was weeks old when adopted, has a single maintainer and is 0.x: a minor release may break its API. The exact pin and the adapter keep a replacement to one module.
- It carries voice over the server's TLS connection only, never over UDP. A lossy mobile link can delay the voice; the bridge logs every stall of the incoming audio to tell.
- It needs a Mumble server 1.5 or later.

## Alternatives considered

- **Fork pymumble.** This is what the maintained bots do, and it means maintaining a Mumble client.
- **pymumble 2.0**, developed on Codeberg. Unreleased, still threaded, and still without server certificate verification.
- **A client in another language as a sidecar.** The Go library gumble has been inactive since 2023; the Rust crates only encode the protocol.
- **Leaving Mumble for WebRTC**, with LiveKit and Pipecat. The mainstream stack for voice agents, at the cost of a new server and a new phone app. It stays the way out if Mumble becomes the problem.
