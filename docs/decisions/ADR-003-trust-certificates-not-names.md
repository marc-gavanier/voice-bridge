# ADR-003 — Trust certificates, not names

**Date**: 2026-11-10
**Status**: accepted

## Context

Whatever the bridge hears becomes an instruction for a Claude Code session that acts with its owner's permissions. The [channels reference](https://code.claude.com/docs/en/channels-reference#gate-inbound-messages) says it plainly: an ungated channel is a prompt injection vector, and the gate must check the sender's identity.

The first bridge trusted two things it could not verify:

- **The speaker's user name.** On Mumble, anyone who knows the server password can join under any unregistered name.
- **The server.** Its TLS connection accepted any certificate, so whoever could stand between the bridge and the server could pose as the server and speak to Claude.

Mumble already authenticates with asymmetric keys: every client holds a certificate, and the server passes each user's certificate hash to the others. The server in use is reachable from the LAN and a VPN only, which narrows who could stand in between without removing the risk.

## Decision

- **Listen to one certificate.** The bridge only takes audio from the user whose client certificate hash equals `speaker_certificate_hash`. A name proves nothing; the private key behind the certificate stays on the phone.
- **Pin the server's certificate.** The bridge trusts only the certificate given as `server_certificate`, refuses protocols older than TLS 1.2, and skips the host name check that a self-signed Murmur certificate cannot pass, as the official client does when it pins a server.
- **Say who was ignored.** The end of each ignored transmission is logged with the sender's name and certificate hash, which shows who tries to talk to the bridge and gives the hash to configure.

## Consequences

- Nothing changes on the server: no account to register, no setting to turn on.
- When the server generates a new certificate, the bridge refuses to connect until the new one is exported to `server_certificate`.
- When the phone's app generates a new certificate, the bridge ignores it until `speaker_certificate_hash` is updated, which the log makes easy.

## Alternatives considered

- **Register the speaker's account on the server and require certificates** (`certrequired`). It protects the name as well, but the name no longer matters to the bridge; it remains an optional extra on the server side.
- **A certificate from a public authority on the server**, such as Let's Encrypt, checked with the host name. Full verification without pinning, at the cost of certificate renewal on the server.
- **Encrypting the conversation another way.** Mumble already encrypts both the control connection and the voice; what was missing was authentication.
