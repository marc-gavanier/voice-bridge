# ADR-021 — Claude plays audio files from one directory

**Date**: 2026-11-14
**Status**: accepted

## Context

The speaker has no screen, so a sound Claude produces or finds, such as samples of the speech at several speeds to compare, can only be described. Claude Code reaches the bridge through the MCP tools of the `voice` channel (`reply`, `end_session`, `board`), and the bridge already decodes an audio file with FFmpeg, through faster-whisper's `decode_audio`, for the hold music ([ADR-014](ADR-014-claude-codes-hooks-tell-when-claude-works.md)).

Two concerns shape how a file can be played:

- Its place in the conversation. A file played straight into the loudspeaker would talk over Claude's voice, ignore the speaker's interruptions and fight the hold music, rules that turn taking already settles for the sentences of a reply.
- What Claude may name. The path comes from Claude, after a transcription that may be wrong, and the bridge reads any file the user can read. Played to the speaker, a wrong file is at worst noise; a file that is not audio, or one of an hour, must not reach the playback buffer, which holds 600 s.

## Decision

The channel gets a fourth tool, `play`, with an absolute `path` and an optional `label`, a few words said before the file. It is always loaded, like the others, and the main agent keeps it, since it only speaks ([ADR-015](ADR-015-the-main-agent-delegates-in-voice-sessions.md)).

The bridge reads only a file whose resolved path, links followed, is inside `clips.directory`, `~/.local/state/voice-bridge/clips` by default, with an audio suffix, no larger than `clips.largest`, 50 MB, that FFmpeg decodes and that lasts no longer than `clips.longest`, 300 s. The file is decoded in a thread when Claude calls the tool, so a refusal answers the call with its reason and Claude can fix it; the tool's description names the directory, and the instructions tell Claude to have a file copied there first.

A decoded file becomes a `Recording` in turn taking, queued with the sentences: the label's sentences, then the recording. Its voice is the recording itself, so the shell skips the speech server for it, and every rule of a sentence holds: it waits for the voice before it, stops the hold music, is cut by the speaker's voice and played again from its start after a mere noise, and is dropped when the speaker's words cut it.

Decoding moves from the hold music ability to the audio library, which both abilities use.

## Consequences

- One mechanism plays Claude's voice and its files: no second path into the loudspeaker to keep in step with interruptions and the hold music.
- A file outside the directory, linked from it or reached with `..`, is refused, and so is anything FFmpeg cannot decode: the bridge never plays another file the user can read. The suffix list keeps out most videos, whose sound FFmpeg would otherwise decode.
- A recording cut by a noise starts over, as a sentence does: fine for short clips, tiresome for a long one.
- A clip is decoded whole in memory, up to 300 s at 48 kHz mono, about 29 MB, until it has played.
- An `instructions_file` written before this change does not mention `play`: Claude still sees the tool and its description, but should be told when to use it.
- `clips.volume` sets the loudness of the clips; the speech's `gain` does not apply, so a clip sounds as the file was made.

## Alternatives considered

- **Any path the user can read**: simplest, but a confused agent or a misheard name could play, or probe the existence of, any file; refusing outside one directory costs only a copy.
- **Writing the file straight to the loudspeaker**: it would overlap Claude's voice and escape interruptions, the rules [ADR-012](ADR-012-words-wait-for-the-speakers-silence-before-reaching-claude.md) and the turn taking scenarios hold.
- **Decoding when the recording's turn comes**: the call would return before the file was checked, and a refusal would only reach the log, never Claude.
- **Cutting a clip at the longest duration instead of refusing it**: Claude would believe the whole file was heard.
- **A Mumble client playing the file on its own**: a second user on the server, outside turn taking, for no gain.
