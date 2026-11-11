from dataclasses import dataclass, replace


@dataclass(frozen=True, slots=True, kw_only=True)
class Track:
    pcm: bytes
    position: int = 0


def next_chunk(track: Track, size: int) -> tuple[bytes, Track]:
    if not track.pcm:
        return b"", track
    chunk, position = b"", track.position
    while len(chunk) < size:
        piece = track.pcm[position : position + size - len(chunk)]
        chunk += piece
        position = (position + len(piece)) % len(track.pcm)
    return chunk, replace(track, position=position)
