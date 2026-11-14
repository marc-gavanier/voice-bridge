from hypothesis import given
from hypothesis import strategies as st

from voice_bridge.features.speaking.domain.text import FEWEST_FIRST_WORDS, SHORTEST_SENTENCE, split_sentences

SPOKEN_TEXT = st.text(alphabet=st.characters(categories=["L", "N", "P", "Zs"]))
WORD = st.text(
    alphabet=st.characters(
        categories=["L", "N", "P"],
        exclude_characters="\N{IDEOGRAPHIC FULL STOP}\N{FULLWIDTH QUESTION MARK}\N{FULLWIDTH EXCLAMATION MARK}",
    ),
    min_size=1,
)
SINGLE_SPACED_TEXT = st.lists(WORD).map(" ".join)
CLAUSE_MARKS = (",", ";", ":", "-", "\N{EN DASH}", "\N{EM DASH}")


def words(text: str) -> list[str]:
    return text.split()


def too_short_before_the_last(sentences: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sentence for sentence in sentences[:-1] if len(sentence) < SHORTEST_SENTENCE)


def first_clause_too_short(sentences: tuple[str, ...]) -> bool:
    cut_first = sentences[:-1][:1]
    return any(first.endswith(CLAUSE_MARKS) and len(words(first)) < FEWEST_FIRST_WORDS for first in cut_first)


@given(SPOKEN_TEXT)
def test_splitting_keeps_every_word_in_order(text: str) -> None:
    assert words(" ".join(split_sentences(text))) == words(text)


@given(SINGLE_SPACED_TEXT)
def test_joining_the_sentences_with_a_space_gives_back_a_single_spaced_text(text: str) -> None:
    assert " ".join(split_sentences(text)) == text


@given(SPOKEN_TEXT)
def test_only_the_last_sentence_may_be_shorter_than_the_shortest_sentence(text: str) -> None:
    assert too_short_before_the_last(split_sentences(text)) == ()


@given(SPOKEN_TEXT)
def test_a_first_sentence_cut_at_a_pause_keeps_at_least_its_fewest_words(text: str) -> None:
    assert not first_clause_too_short(split_sentences(text))
