# Security policy

## Supported versions

voice-bridge has no release yet. Only the `main` branch is supported: fixes land there, and are not backported.

## Reporting a vulnerability

Do not open a public issue for a vulnerability. Report it privately through [GitHub's private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability): open the repository's **Security** tab and choose [**Report a vulnerability**](https://github.com/marc-gavanier/voice-bridge/security/advisories/new).

Include in the report:

- the commit of `main` you tested;
- the steps to reproduce, as short as possible;
- what an attacker gains, and what they need beforehand, such as the server password or a place on the network.

Say which tools helped you find or write up the issue, and check their findings yourself before sending them.

## What happens next

The report stays private between you and the maintainer while it is assessed, in the draft advisory GitHub opens for it. If it is confirmed, the fix is prepared in private and merged into `main`, then the advisory is published, crediting you unless you prefer otherwise. If it is not, the advisory says why and is closed.

## Scope

Whatever the bridge hears becomes an instruction for a Claude Code session that acts with its owner's permissions, so the bridge must only listen to its owner. It holds a Mumble server password, pins the server's certificate and listens to one speaker's certificate ([ADR-003](docs/decisions/ADR-003-trust-certificates-not-names.md)). In scope:

- anyone other than the configured speaker getting words into the Claude Code session, or the speaker's identity being forged;
- the bridge accepting a server other than the pinned one, or a protocol older than TLS 1.2;
- the server password leaking, through the log or otherwise.

Out of scope, to report to their own projects: Claude Code and its channels, the Mumble server and apps, pymumble-rev, Whisper, Silero and Voxtral. Attacks that need the owner's account on the machine running the bridge are out of scope too, since that account already holds the configuration and the Claude Code session.
