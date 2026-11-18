from voice_bridge.features.speaking.abilities.announce.domain.wording import Wording, every_sentence, sentence_for

WORDING = Wording(
    at_work=("Two at work.", "Three at work."), many_at_work="Many at work.", voice_lost="The voice is lost."
)


def test_no_agent_at_work_has_no_announcement() -> None:
    assert sentence_for(WORDING, 0) is None


def test_a_single_agent_at_work_has_no_announcement() -> None:
    assert sentence_for(WORDING, 1) is None


def test_two_agents_at_work_are_announced_with_the_first_count() -> None:
    assert sentence_for(WORDING, 2) == "Two at work."


def test_the_last_counted_agents_at_work_are_announced_with_the_last_count() -> None:
    assert sentence_for(WORDING, 3) == "Three at work."


def test_more_agents_at_work_than_counted_are_many() -> None:
    assert sentence_for(WORDING, 4) == "Many at work."


def test_every_sentence_is_listed_to_be_voiced() -> None:
    assert every_sentence(WORDING) == ("Two at work.", "Three at work.", "Many at work.", "The voice is lost.")
