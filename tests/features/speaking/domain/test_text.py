from voice_bridge.features.speaking.domain.text import for_the_ear, split_sentences


def test_sentences_are_cut_on_their_final_punctuation() -> None:
    text = "D'accord, je regarde ça maintenant. Il reste deux points à trancher ! Tu préfères lequel ?"
    assert split_sentences(text) == (
        "D'accord, je regarde ça maintenant.",
        "Il reste deux points à trancher !",
        "Tu préfères lequel ?",
    )


def test_a_very_short_sentence_is_merged_with_the_next_one() -> None:
    assert split_sentences("Oui. Je lance la commande tout de suite.") == ("Oui. Je lance la commande tout de suite.",)


def test_blank_text_has_no_sentence() -> None:
    assert split_sentences("   ") == ()


def test_markdown_emphasis_code_and_links_are_read_as_plain_text() -> None:
    assert for_the_ear("**Bon** `fichier.py` : voir [la doc](https://x.y)\n- point un") == (
        "Bon fichier.py : voir la doc\npoint un"
    )


def test_code_blocks_are_not_read_aloud() -> None:
    assert for_the_ear("Voici.\n```python\nprint(1)\n```\nFini.") == "Voici.\n\nFini."
