from voice_bridge.features.speaking.domain.acknowledgement import fresh


def test_the_last_sentence_played_is_left_out() -> None:
    assert fresh(("D'accord.", "Entendu.", "Noté."), "Entendu.") == ("D'accord.", "Noté.")


def test_a_single_sentence_is_played_again() -> None:
    assert fresh(("D'accord.",), "D'accord.") == ("D'accord.",)


def test_every_sentence_is_fresh_before_any_was_played() -> None:
    assert fresh(("D'accord.", "Entendu."), None) == ("D'accord.", "Entendu.")
