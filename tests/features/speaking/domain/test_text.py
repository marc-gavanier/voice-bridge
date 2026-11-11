from voice_bridge.features.speaking.domain.text import for_the_ear, split_sentences


def test_sentences_are_cut_on_their_final_punctuation() -> None:
    text = "Alright, I am looking into it right away. Two points are left to settle ! Which one do you prefer ?"
    assert split_sentences(text) == (
        "Alright, I am looking into it right away.",
        "Two points are left to settle !",
        "Which one do you prefer ?",
    )


def test_a_very_short_sentence_is_merged_with_the_next_one() -> None:
    assert split_sentences("Yes. I am running the command right away.") == (
        "Yes. I am running the command right away.",
    )


def test_blank_text_has_no_sentence() -> None:
    assert split_sentences("   ") == ()


def test_markdown_emphasis_code_and_links_are_read_as_plain_text() -> None:
    assert for_the_ear("**Good** `file.py` : see [the docs](https://x.y)\n- point one") == (
        "Good file.py : see the docs\npoint one"
    )


def test_code_blocks_are_not_read_aloud() -> None:
    assert for_the_ear("Here.\n```python\nprint(1)\n```\nDone.") == "Here.\n\nDone."


def test_a_sentence_of_exactly_the_shortest_length_stands_alone() -> None:
    assert split_sentences("Twelve char. Another sentence.") == ("Twelve char.", "Another sentence.")


def test_merging_a_short_sentence_keeps_the_sentences_before_it() -> None:
    assert split_sentences("A first long sentence. Yes. Then the rest.") == (
        "A first long sentence.",
        "Yes. Then the rest.",
    )
