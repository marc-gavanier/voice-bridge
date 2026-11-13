from hypothesis import given
from hypothesis import strategies as st

from voice_bridge.features.speaking.abilities.announce.domain.wording import Wording, every_sentence, sentence_for

SENTENCES = st.text(min_size=1, max_size=10)
WORDINGS = st.builds(
    Wording,
    at_work=st.lists(SENTENCES, max_size=6).map(tuple),
    many_at_work=SENTENCES,
    finished=st.lists(SENTENCES, max_size=6).map(tuple),
    many_left=SENTENCES,
    none_at_work=SENTENCES,
)


@given(wording=WORDINGS, at_work=st.integers(min_value=-3, max_value=20), finished=st.booleans())
def test_every_announcement_is_one_of_the_sentences_voiced_at_startup(
    *, wording: Wording, at_work: int, finished: bool
) -> None:
    assert sentence_for(wording, at_work, finished=finished) in every_sentence(wording)
