from voice_bridge.features.speaking.abilities.acknowledge.domain.candidates import Candidates, candidates

POOLS = (("Let me see.", "Good question."), (), ("Alright.", "Fine."))


def test_there_is_no_candidate_before_any_pool_is_recorded() -> None:
    assert candidates((), 0, {}) is None


def test_the_kind_of_the_words_chooses_the_pool() -> None:
    assert candidates(POOLS, 0, {}) == Candidates(pool=0, sentences=("Let me see.", "Good question."))


def test_words_of_no_kind_get_the_last_pool() -> None:
    assert candidates(POOLS, None, {}) == Candidates(pool=2, sentences=("Alright.", "Fine."))


def test_an_empty_pool_has_no_candidate() -> None:
    assert candidates(POOLS, 1, {}) is None


def test_the_last_sentence_of_the_pool_is_not_a_candidate() -> None:
    assert candidates(POOLS, 0, {0: "Let me see."}) == Candidates(pool=0, sentences=("Good question.",))


def test_the_last_sentence_of_another_pool_stays_a_candidate() -> None:
    assert candidates(POOLS, 0, {2: "Let me see."}) == Candidates(pool=0, sentences=("Let me see.", "Good question."))
