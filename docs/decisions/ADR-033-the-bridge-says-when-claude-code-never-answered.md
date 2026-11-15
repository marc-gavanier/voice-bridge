# ADR-033 — The bridge says when Claude Code never answered

**Date**: 2026-11-15
**Status**: accepted

## Context

On 2026-11-15, from 21:01 to 22:17, the speaker was out running and heard only the hold music: every sentence was forwarded, acknowledged with nothing and followed by music, and Claude never replied. The session started by `scripts/claude-voice.sh` was waiting on its screen for the warning that `--dangerously-load-development-channels` shows at every launch, « WARNING: Loading development channels », with « I am using this for local development » or « Exit ». Claude Code had already started the `voice` channel, so the bridge heard and forwarded the words, but Claude Code queued them until someone confirmed. No hook ran, and the hold music, which [ADR-014](ADR-014-claude-codes-hooks-tell-when-claude-works.md) starts from the moment the words are forwarded, never stopped.

The dialog cannot be avoided. The [channels reference](https://code.claude.com/docs/en/channels-reference#test-during-the-research-preview) says that the development flag skips the allowlist « after a confirmation prompt », and asks to run it in an interactive session for that reason. Claude Code 2.1.325 shows the dialog unless channels are off for the session, the provider is not Anthropic's API, or the organization's policy blocks channels: no setting records the acceptance, as `skipDangerousModePermissionPrompt` does for the bypass permissions mode. A custom channel loads only through this flag during the research preview; `--channels` accepts only the allowlisted plugins, and `allowedChannelPlugins` belongs to Team and Enterprise organizations.

The bridge also gets no sign from the channel: Claude Code does not acknowledge a channel notification, and drops or queues it silently.

## Decision

- Turn taking keeps whether any of Claude Code's hooks has told the bridge that Claude works or is done since the bridge started. Words forwarded before that wait `claude.unanswered_after`, 10 s by default. When the wait ends and still no hook was heard, the bridge stops counting Claude as working, so that the hold music neither starts nor comes back, and says the language file's `unanswered` sentence, queued and voiced like a reply: it stops the music when its voice is ready, waits for the speaker and is cut by their voice.
- Only the wait of the latest words counts. Each new message waits again, so each one is told while the session stays blocked.
- A reply from Claude does not end the wait: the bridge's own greeting arrives as a reply too, and could come after the first words while Voxtral starts.
- Each of the nine language files carries the sentence. French: « Claude ne répond pas : la session attend sans doute une confirmation sur l'écran de l'ordinateur. »

## Consequences

- A session blocked before its first turn is told within 10 s of each message instead of playing music forever. The speaker can confirm on the screen, or from the Claude app once `/remote-control` is on, and the session then takes every queued message.
- UserPromptSubmit reaches the bridge in about 0.3 s in the log, so 10 s leaves room for a hook started with `uv run` on a cold cache.
- Once a hook was heard, the bridge never says it again in the session: words Claude Code does not take at once are then queued behind its turn, which is normal. A dialog that blocks a session later, such as a permission prompt, is not detected.
- A session whose hooks never reach the bridge, such as one started without the launcher, hears the sentence after each message that Claude does not answer within 10 s; the board already calls such hooks unreliable ([ADR-022](ADR-022-the-board-of-agents-heals-and-says-when-it-cannot-be-trusted.md)).
- Before Voxtral is ready, the sentence cannot be voiced: its synthesis fails and the music stops, without a word.
- The sentences of the eight other languages were written by translation and are unreviewed by native speakers.

## Alternatives considered

- **A setting that skips the dialog**: none exists for development channels; the one for the bypass permissions mode concerns another dialog.
- **Answering the dialog from the launcher**, by sending keys to Claude Code's terminal through `tmux` or `expect`: it accepts a security warning on the speaker's behalf, couples the launcher to the dialog's layout, and the launcher `exec`s Claude Code in the user's own terminal.
- **Reading Claude Code's screen** for the dialog's title: the bridge runs as an MCP server under Claude Code and has no access to its terminal.
- **A `SessionStart` hook** telling the bridge that the session runs: whether Claude Code runs it before or after the dialog is not documented, and a message forwarded with no hook following it is the symptom the speaker suffers from, whatever its cause.
