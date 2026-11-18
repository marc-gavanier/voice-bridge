# ADR-040 — Claude plays clips streamed from a list of directories

**Date**: 2026-11-18
**Status**: accepted, partly supersedes [ADR-021](ADR-021-claude-plays-audio-files-from-one-directory.md) for the directory, the limits and when a clip is decoded, and replaces the bound that `clips.longest` gave the player's queue in [ADR-038](ADR-038-the-transport-pulls-what-it-sends-from-one-player.md)

## Context

ADR-021 let Claude play a file only from one directory, `clips.directory`, and decoded it whole when Claude called `play`, so it capped a clip at 300 s and 50 MB: a decoded clip stayed in memory until it had played, and the playback buffer held 600 s. Two uses fell outside: a file already in a folder the user means to share, such as a music library, had to be copied first, and an album or a long recording could not be played at all.

Since then, ADR-035 put where audio comes from behind an audio source port, with a folder as its adapter, and the decoding port gives frames as they come (#87). ADR-038 made the player the only writer to the transport, with a queue that has no bound, kept short by `clips.longest` and the hold music's one second ahead.

## Decision

- **A list of directories.** `clips.directories` lists the folders `play` reads from, with their subfolders, at least one; `~/.local/state/voice-bridge/clips` alone by default. The folder source accepts a path inside any of them, with the rules of ADR-021 otherwise unchanged: absolute, resolved with links followed, an audio suffix, a file. The tool's description lists every folder.
- **Checked on the call, decoded when it plays.** On the call, the bridge only checks the clip: the source accepts its path and FFmpeg decodes its first sound, so a refusal still answers Claude with its reason. The recording carries its path through turn taking; when its turn comes, the conversation reads it through a `Recordings` port, as it reads the voice of a sentence, and the clip stream finds the file again in the source and decodes it as it plays.
- **Paced ahead of the ear.** The stream hears the clip in pieces of half a second at `clips.volume`, sent at most five seconds ahead of the time they take to play. This lead bounds the player's queue for a clip of any length.
- **No size or length limit.** `clips.largest` and `clips.longest` are removed. A config that still sets them, or `clips.directory`, is refused with a message that names what replaced them, rather than ignored.

## Consequences

- A clip of any length plays with a few seconds of audio in memory, and starts as soon as its first pieces are decoded.
- A file that changes or goes away between the call and its turn is refused or cut short in the log, `clip no longer played` or `clip cut short`, and the next sentence follows, as after a failed synthesis; Claude is not told, since the call has already returned.
- A recording cut by a noise starts over from its beginning, as ADR-021 said, which is now more tiresome for a long file.
- Each folder listed widens what a misheard path can reach: the user chooses them, and nothing outside them is read.
- An old config with `clips.directory`, `clips.largest` or `clips.longest` stops the bridge at startup until it is fixed.

## Alternatives considered

- **Keeping one directory and linking other folders into it**: ADR-021 refuses a link to a file outside the directory, on purpose; allowing links would let any link reach any file.
- **Keeping the limits and raising them**: a higher cap only moves the album that does not fit, and keeps a whole clip in memory.
- **Decoding only when the recording's turn comes, without a check on the call**: ADR-021 set it aside, since a refusal would reach the log and never Claude; checking the first sound keeps that answer for the common mistakes.
- **Handing the frames straight to the player**: each frame of a few milliseconds would cross turn taking as its own event; pieces of half a second keep the events few.
- **Accepting the former keys as aliases**: two names for one setting, and a silent change of meaning for `clips.directory`, which named one folder and now would name a list.
