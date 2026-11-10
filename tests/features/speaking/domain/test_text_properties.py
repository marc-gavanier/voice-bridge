from hypothesis import given
from hypothesis import strategies as st

from voice_bridge.features.speaking.domain.text import SHORTEST_SENTENCE, split_sentences

SPOKEN_TEXT = st.text(alphabet=st.characters(categories=["L", "N", "P", "Zs"]))


def words(text: str) -> list[str]:
    return text.split()


def too_short_before_the_last(sentences: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sentence for sentence in sentences[:-1] if len(sentence) < SHORTEST_SENTENCE)


@given(SPOKEN_TEXT)
def test_splitting_keeps_every_word_in_order(text: str) -> None:
    assert words(" ".join(split_sentences(text))) == words(text)


@given(SPOKEN_TEXT)
def test_only_the_last_sentence_may_be_shorter_than_the_shortest_sentence(text: str) -> None:
    assert too_short_before_the_last(split_sentences(text)) == ()
