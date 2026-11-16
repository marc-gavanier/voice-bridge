from array import array
from dataclasses import dataclass, field

import pytest

from voice_bridge.features.speaking.abilities.mix.domain.mixing import Layer
from voice_bridge.features.speaking.abilities.mix.domain.played import Played
from voice_bridge.features.speaking.abilities.mix.domain.ports import Reference
from voice_bridge.features.speaking.abilities.mix.implementation.player import Player

FRAME = len(array("h", (0, 0)).tobytes())


def samples(*values: int) -> bytes:
    return array("h", values).tobytes()


@dataclass
class RecordedReference:
    played: list[Played] = field(default_factory=list[Played])

    def __call__(self, played: Played, /) -> None:
        self.played.append(played)


def pulled(player: Player, count: int) -> list[bytes]:
    return [player(FRAME) for _ in range(count)]


def player_heard_by(reference: Reference) -> Player:
    return Player(clock=lambda: 7.5, reference=reference)


def test_the_player_gives_the_transport_what_it_was_asked_to_play() -> None:
    player = Player(clock=lambda: 0.0)
    player.play(Layer.VOICE, samples(1, 2))
    assert player(FRAME) == samples(1, 2)


def test_the_player_gives_nothing_while_it_has_no_whole_frame() -> None:
    player = Player(clock=lambda: 0.0)
    player.play(Layer.VOICE, samples(1))
    assert player(FRAME) == b""


def test_the_player_mixes_the_layers() -> None:
    player = Player(clock=lambda: 0.0)
    player.play(Layer.MUSIC, samples(1, 2))
    player.play(Layer.VOICE, samples(3, 4))
    player.play(Layer.MUSIC, samples(10, 20))
    assert pulled(player, 2) == [samples(1, 2), samples(13, 24)]


def test_stopping_drops_every_layer() -> None:
    player = Player(clock=lambda: 0.0)
    player.play(Layer.VOICE, samples(1, 2))
    player.play(Layer.MUSIC, samples(3, 4))
    player.stop()
    assert player(FRAME) == b""


def test_each_frame_played_is_given_as_the_reference_with_its_time() -> None:
    reference = RecordedReference()
    player = player_heard_by(reference)
    player.play(Layer.VOICE, samples(1, 2))
    _ = player(FRAME)
    assert reference.played == [Played(pcm=samples(1, 2), at=7.5)]


def test_no_reference_is_given_when_nothing_is_played() -> None:
    reference = RecordedReference()
    _ = player_heard_by(reference)(FRAME)
    assert reference.played == []


def test_a_player_without_a_reference_plays_all_the_same() -> None:
    player = Player(clock=lambda: 0.0)
    player.play(Layer.VOICE, samples(1, 2))
    assert player(FRAME) == samples(1, 2)


def test_a_channel_plays_on_its_layer() -> None:
    player = Player(clock=lambda: 0.0)
    player.channel(Layer.MUSIC).play(samples(1, 2))
    player.channel(Layer.VOICE).play(samples(3, 4))
    player.channel(Layer.MUSIC).play(samples(5, 6))
    assert pulled(player, 2) == [samples(1, 2), samples(8, 10)]


def test_a_channel_stops_the_whole_player() -> None:
    player = Player(clock=lambda: 0.0)
    player.play(Layer.MUSIC, samples(1, 2))
    player.channel(Layer.VOICE).stop()
    assert player(FRAME) == b""


def test_the_first_audio_played_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("INFO")
    Player(clock=lambda: 0.0).play(Layer.VOICE, samples(1))
    assert "playback starts" in caplog.text


def test_audio_added_while_some_is_queued_is_not_logged(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("INFO")
    player = Player(clock=lambda: 0.0)
    player.play(Layer.VOICE, samples(1))
    caplog.clear()
    player.play(Layer.VOICE, samples(2))
    assert caplog.text == ""
