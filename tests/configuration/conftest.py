from collections.abc import Callable
from functools import cache

import pytest

from voice_bridge.configuration.language import language_pack
from voice_bridge.configuration.settings import Language, UnderstandingSettings
from voice_bridge.features.speaking.abilities.acknowledge.domain.candidates import fallback
from voice_bridge.features.understanding.abilities.understand.implementation.embeddings import (
    Encoder,
    Router,
    load_encoder,
    router,
)
from voice_bridge.features.understanding.abilities.understand.implementation.understand import Understanding
from voice_bridge.features.understanding.domain.meaning import Route


@pytest.fixture(scope="session")
def encoder() -> Encoder:
    settings = UnderstandingSettings()
    return load_encoder(settings.model, settings.revision)


@pytest.fixture(scope="session")
def route_of(encoder: Encoder) -> Callable[[Language, str], str]:
    @cache
    def routing(language: Language) -> tuple[Router, tuple[Route, ...]]:
        pack = language_pack(language)
        routes = tuple(
            Route(
                name=each.name,
                threshold=UnderstandingSettings().threshold if each.threshold is None else each.threshold,
                stops=each.stops,
                answers=each.answers,
            )
            for each in pack.acknowledgements
        )
        scores = router(encoder, [each.examples for each in pack.acknowledgements])
        return scores, routes

    def route(language: Language, words: str) -> str:
        scores, routes = routing(language)
        meaning = Understanding(scores=scores, routes=routes)(words)
        return fallback(words) if meaning.route is None else routes[meaning.route].name

    return route
