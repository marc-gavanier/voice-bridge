from voice_bridge.features.speaking.domain.shuffle import next_pass


def test_a_pass_keeps_the_order_it_was_shuffled_in() -> None:
    assert next_pass(("b", "c", "a"), last="a") == ("b", "c", "a")


def test_a_pass_never_starts_with_the_last_track_of_the_previous_one() -> None:
    assert next_pass(("a", "b", "c"), last="a") == ("b", "c", "a")


def test_the_first_pass_keeps_its_order() -> None:
    assert next_pass(("a", "b"), last=None) == ("a", "b")


def test_a_single_track_plays_again() -> None:
    assert next_pass(("a",), last="a") == ("a",)


def test_an_empty_pass_stays_empty() -> None:
    assert next_pass((), last="a") == ()
