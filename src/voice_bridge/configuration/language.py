from dataclasses import dataclass
from importlib.resources import files
from typing import TYPE_CHECKING, Final, assert_never

if TYPE_CHECKING:
    from pathlib import Path

    from voice_bridge.configuration.settings import Language


@dataclass(frozen=True, slots=True, kw_only=True)
class LanguagePack:
    whisper_code: str
    voice: str
    greeting: str
    acknowledgements: tuple[tuple[str, tuple[str, ...]], ...]
    reply_tool_description: str
    reply_text_description: str
    reply_working_description: str
    hallucinations: frozenset[str]
    hallucination_prefixes: tuple[str, ...]
    instructions: str


def _words(*words: str) -> str:
    return rf"\b({'|'.join(words)})\b"


ENGLISH_ACKNOWLEDGEMENTS: Final = (
    (r"(\.\.\.|…)$|^(and|so|but|or|well)[ .,]*$", ("Yes?", "I'm listening.", "Go on.", "Carry on.", "And then?")),
    (
        r"\b(can you hear me|do you hear me|are you there|are you still|are you waiting)\b",
        ("Yes, I'm here.", "I can hear you.", "Still here.", "I'm here, yes.", "Loud and clear."),
    ),
    (
        r"\b(thanks|thank you|well done|great job|nice work)\b",
        ("Thanks!", "My pleasure.", "Glad it helps.", "Anytime."),
    ),
    (
        r"\b(let's stop|we can stop|goodbye|bye|that's all|we're done)\b",
        ("Alright, let's stop.", "Sounds good.", "See you later.", "Fine, we stop here."),
    ),
    (
        r"\b(cut|cuts|broken|bug|weird|strange|problem|issue|glitch|latency|delay|lag|i counted|too fast)\b",
        ("Let me look into that.", "I'll check.", "Noted, I'm looking.", "I'll have a look.", "Oh, let me see."),
    ),
    (
        r"\b(i (re)?started|i restarted|i relaunched|restarting)\b",
        ("Got it.", "Great, noted.", "Alright, here we go.", "Good."),
    ),
    (
        _words(
            "can you",
            "could you",
            "please",
            "look at",
            "check",
            "analy[sz]e",
            "i'd like you to",
            "i want you to",
            "make",
            "run",
            "prepare",
            "explain",
            "list",
            "show",
        ),
        ("On it.", "Let me look.", "I'm on it.", "Here we go.", "Sure, looking now.", "Let me see to that."),
    ),
    (
        r"\?$|^(is|are|do|does|did|can|could|why|how|what|when|where|which|who)\b",
        ("Let's see.", "Good question.", "Let me think.", "Let me check.", "Hold on, I'll look."),
    ),
    (
        r"\b(i wonder|the idea|we could|i think|i feel|it would be|i have an idea)\b",
        ("Interesting.", "I see the idea.", "Oh, I see.", "I'm listening.", "That makes sense."),
    ),
    (r"^(no|nope|no need|never mind)\b", ("Alright.", "Understood.", "Fine, we leave it.", "No problem.", "Got it.")),
    (
        r"^(yes|yeah|yep|ok|okay|sure|go ahead|sounds good|fine)\b",
        ("Perfect.", "Great.", "Alright.", "Very well.", "Here we go."),
    ),
    ("", ("Okay.", "Got it.", "I see.", "Noted.", "Understood.", "Right.")),
)

FRENCH_ACKNOWLEDGEMENTS: Final = (
    (
        r"(\.\.\.|…)$|^(et|donc|mais|ou|alors|enfin)[ .,]*$",
        ("Oui ?", "Je t'écoute.", "Vas-y.", "Continue.", "Et donc ?"),
    ),
    (
        r"\b(tu m'entends|tu ne m'entends|tu n'entends|tu m'as entendu|tu es encore en train|tu attends|tu es là)\b",
        ("Oui, je suis là.", "Je t'entends.", "Je suis là, oui.", "Toujours là.", "Oui, je t'entends bien."),
    ),
    (
        r"\b(merci|bravo|bon travail|bien joué)\b",
        ("Merci !", "Avec plaisir.", "Merci, ça fait plaisir.", "De rien.", "Content que ça te plaise."),
    ),
    (
        r"\b(on arrête|on peut arrêter|fin à la conversation|au revoir|c'est fini|arrêter la session)\b",
        ("D'accord, on s'arrête.", "Très bien.", "Ça marche.", "À plus tard.", "Entendu, on s'arrête là."),
    ),
    (
        _words(
            "coupé",
            "coupure",
            "je ne t'entends",
            "je ne reçois",
            "bug",
            "bizarre",
            "problème",
            "artefacts?",
            "latence",
            "délai",
            "j'ai compté",
            "trop vite",
            "erratiques?",
            "ne marche",
        ),
        (
            "Ah, je regarde ça.",
            "Je vérifie.",
            "Noté, je cherche.",
            "Je vais voir ça.",
            "Ah, mince.",
            "Je jette un œil.",
        ),
    ),
    (
        r"\b(j'ai (re)?démarré|j'ai (re)?lancé|je relance|redémarré)\b",
        ("Bien reçu.", "Parfait, c'est noté.", "Super.", "D'accord, on y va.", "Très bien."),
    ),
    (
        _words(
            "tu peux",
            "peux-tu",
            "regarde",
            "analyse",
            "je voudrais que tu",
            "je veux que tu",
            "fais",
            "lance",
            "prépare",
            "commence",
            "explique",
            "donne",
            "liste",
            "vérifie",
            "cherche",
            "ajoute",
            "répète",
            "montre",
        ),
        (
            "Je regarde.",
            "Je m'en occupe.",
            "Je m'y mets.",
            "C'est parti.",
            "Ça marche, je regarde.",
            "D'accord, je lance.",
            "Je vois ça.",
            "Laisse-moi regarder.",
        ),
    ),
    (
        r"\?$|^(est-ce|pourquoi|comment|qu'est-ce|quel|quelle|quand|où|combien)\b",
        ("Voyons.", "Bonne question.", "Je réfléchis.", "Laisse-moi voir.", "Je vérifie.", "Attends, je regarde."),
    ),
    (
        r"\b(je me demande|l'idée|on pourrait|je pense que|je trouve que|ce serait|j'ai une idée)\b",
        ("Intéressant.", "Je vois l'idée.", "Ah, d'accord.", "Je t'écoute.", "Ça se tient."),
    ),
    (
        r"^(non|pas besoin|pas nécessairement|tant pis)\b",
        ("D'accord.", "Compris.", "Très bien, on laisse.", "Pas de souci.", "Entendu.", "Ça marche."),
    ),
    (
        r"^(oui|ouais|ok|d'accord|ça me va|on fait|on garde|vas-y|parfait|c'est bon)\b",
        ("Parfait.", "Ça marche.", "Super.", "Très bien.", "C'est parti.", "Bien."),
    ),
    ("", ("D'accord.", "Entendu.", "Je vois.", "Noté.", "Compris.", "Je note.", "Ah, d'accord.")),
)


def _packaged_instructions(language: Language) -> str:
    return (
        files("voice_bridge.configuration")
        .joinpath("instructions", f"{language}.md")
        .read_text(encoding="utf-8")
        .strip()
    )


def language_pack(language: Language) -> LanguagePack:
    match language:
        case "en":
            return LanguagePack(
                whisper_code="en",
                voice="neutral_female",
                greeting="I'm listening.",
                acknowledgements=ENGLISH_ACKNOWLEDGEMENTS,
                reply_tool_description="Speak a reply aloud in the user's headset",
                reply_text_description="The text to speak, written for the ear",
                reply_working_description=(
                    "True when the text announces work you are about to do: hold music then plays until your next reply"
                ),
                hallucinations=frozenset({"", "you", "thank you", "thanks for watching"}),
                hallucination_prefixes=("subtitles by",),
                instructions=_packaged_instructions(language),
            )
        case "fr":
            return LanguagePack(
                whisper_code="fr",
                voice="fr_female",
                greeting="Je t'écoute.",
                acknowledgements=FRENCH_ACKNOWLEDGEMENTS,
                reply_tool_description="Dire une réponse à voix haute dans le casque de l'utilisateur",
                reply_text_description="Le texte à prononcer, rédigé pour l'oreille",
                reply_working_description=(
                    "Vrai quand le texte annonce un travail que tu vas faire : "
                    "une musique d'attente joue alors jusqu'à ta réponse suivante"
                ),
                hallucinations=frozenset({"", "merci", "je vous prie"}),
                hallucination_prefixes=("sous-titrage",),
                instructions=_packaged_instructions(language),
            )
        case _:
            assert_never(language)


def load_instructions(path: Path, default: str) -> str:
    return path.read_text(encoding="utf-8").strip() if path.exists() else default
