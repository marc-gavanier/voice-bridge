import re
from functools import reduce
from typing import Final

SHORTEST_SENTENCE: Final = 12
FEWEST_FIRST_WORDS: Final = 4
SPACED_SENTENCE_END: Final = r"(?<=[.!?\N{HORIZONTAL ELLIPSIS}\N{ARABIC QUESTION MARK}\N{DEVANAGARI DANDA}])\s+"
CJK_SENTENCE_END: Final = (
    r"(?<=[\N{IDEOGRAPHIC FULL STOP}\N{FULLWIDTH QUESTION MARK}\N{FULLWIDTH EXCLAMATION MARK}])\s*"
)
SENTENCE_END: Final = re.compile(f"{SPACED_SENTENCE_END}|{CJK_SENTENCE_END}")
CLAUSE_END: Final = re.compile(r"(?<=[,;:\-\N{EN DASH}\N{EM DASH}])\s+")
MARKDOWN_RULES: Final = (
    (re.compile(r"```.*?```", re.DOTALL), ""),
    (re.compile(r"\[([^\]]+)\]\([^)]+\)"), r"\1"),
    (re.compile(r"[*_`#]+"), ""),
    (re.compile(r"^\s*[-\N{EN DASH}\N{EM DASH}]\s+", re.MULTILINE), ""),
)


def _gather(sentences: tuple[str, ...], part: str) -> tuple[str, ...]:
    if sentences and len(sentences[-1]) < SHORTEST_SENTENCE:
        return (*sentences[:-1], f"{sentences[-1]} {part}")
    return (*sentences, part)


def _first_clause(sentence: str) -> tuple[str, ...]:
    pauses = CLAUSE_END.finditer(sentence)
    cut = next((pause for pause in pauses if len(sentence[: pause.start()].split()) >= FEWEST_FIRST_WORDS), None)
    if cut is None:
        return (sentence,)
    return sentence[: cut.start()], sentence[cut.end() :]


def _shorten_the_first(sentences: tuple[str, ...]) -> tuple[str, ...]:
    if not sentences:
        return ()
    return reduce(_gather, (*_first_clause(sentences[0]), *sentences[1:]), ())


def split_sentences(text: str) -> tuple[str, ...]:
    parts = (part for part in SENTENCE_END.split(text.strip()) if part)
    return _shorten_the_first(reduce(_gather, parts, ()))


def for_the_ear(text: str) -> str:
    return reduce(lambda result, rule: rule[0].sub(rule[1], result), MARKDOWN_RULES, text).strip()
