from voice_bridge.features.speaking.abilities.announce.domain.wording import Wording, every_sentence, sentence_for

WORDING = Wording(
    at_work=("One at work.", "Two at work."),
    many_at_work="Many at work.",
    finished=("One finished, one left.", "One finished, two left."),
    many_left="One finished, many left.",
    none_at_work="None at work.",
)


def test_one_agent_at_work_is_announced_with_the_first_count() -> None:
    assert sentence_for(WORDING, 1, finished=False) == "One at work."


def test_the_last_counted_agents_at_work_are_announced_with_the_last_count() -> None:
    assert sentence_for(WORDING, 2, finished=False) == "Two at work."


def test_more_agents_at_work_than_counted_are_many() -> None:
    assert sentence_for(WORDING, 3, finished=False) == "Many at work."


def test_a_finished_agent_is_announced_with_the_one_left() -> None:
    assert sentence_for(WORDING, 1, finished=True) == "One finished, one left."


def test_a_finished_agent_is_announced_with_the_last_count_left() -> None:
    assert sentence_for(WORDING, 2, finished=True) == "One finished, two left."


def test_a_finished_agent_with_more_left_than_counted_leaves_many() -> None:
    assert sentence_for(WORDING, 3, finished=True) == "One finished, many left."


def test_the_last_agent_finished_leaves_none_at_work() -> None:
    assert sentence_for(WORDING, 0, finished=True) == "None at work."


def test_no_agent_at_work_is_announced_as_none() -> None:
    assert sentence_for(WORDING, 0, finished=False) == "None at work."


def test_every_sentence_is_listed_to_be_voiced() -> None:
    assert every_sentence(WORDING) == (
        "One at work.",
        "Two at work.",
        "Many at work.",
        "One finished, one left.",
        "One finished, two left.",
        "One finished, many left.",
        "None at work.",
    )
