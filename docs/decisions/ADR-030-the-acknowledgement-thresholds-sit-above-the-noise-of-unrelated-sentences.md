# ADR-030 — The acknowledgement thresholds sit above the noise of unrelated sentences

**Date**: 2026-11-15
**Status**: accepted, revises the thresholds of [ADR-010](ADR-010-semantic-routing-chooses-the-acknowledgement-and-detects-a-stop.md); to re-validate on the next sessions

## Context

[ADR-010](ADR-010-semantic-routing-chooses-the-acknowledgement-and-detects-a-stop.md) set `understanding.threshold` to 0.5 for every route but stop, which needs 0.75, from 50 sentences. On the session of 2026-11-15, the speaker heard many acknowledgements that did not fit: « Je vois l'idée. » after a go-ahead, « Je suis là. » or « Je t'écoute. » after a question, « À bientôt. » in the middle of work.

The utterance events of the telemetry record, for each forwarded sentence, the route taken and the acknowledgement played. For the 28 sentences of that session, the ranking of every route was computed again with the language file of the run, and each sentence was given, by hand, the set of routes whose acknowledgement would fit it. Two things came out:

- Between two unrelated French sentences, MiniLM gives a cosine similarity of 0.5 to 0.65. A long sentence about anything finds an example above 0.5 on some route: « Tu ne m'as peut-être pas entendu parce qu'il y a eu encore un problème avec Mumble… » took presence at 0.59, « Sur le ticket de 44 qui parlait de la fluidification de la parole, il resterait quoi à faire… » took problem at 0.53. The threshold of 0.5 was below the noise.
- The routes whose acknowledgement commits most were the ones that misfired worst: a wrong presence answers « Je suis là. » and plays no hold music, a wrong end of session says goodbye while work goes on. Four sentences, none of them about presence, took presence at 0.59 to 0.63, and « Ouais ça me va, prépare ça maintenant… on l'activera quand on redémarrera le pont » took end at 0.70.

Several rules were simulated on the 28 sentences:

| Rule | Right | Wrong | Neutral |
|---|---|---|---|
| 0.5, stop 0.75 (ADR-010) | 14 | 9 | 5 |
| 0.6, stop 0.75 | 10 | 4 | 14 |
| 0.7, stop 0.75 | 6 | 2 | 20 |
| 0.8, stop 0.75 | 3 | 0 | 25 |
| 0.6, stop 0.75, and a margin of 0.05 over the second route | 9 | 3 | 16 |
| 0.6, presence 0.7, end and stop 0.75 | 11 | 1 | 16 |

The one wrong pick left by the last rule was a language file error: « Oui, c'est plus clair. Si c'est faisable dans un temps raisonnable, on peut lancer ça maintenant. » took idea at 0.77, from the example « Je pense qu'on peut le faire maintenant. », which launches the work rather than proposing an idea.

## Decision

- `understanding.threshold` defaults to 0.6.
- Each language file sets 0.7 on the presence route and 0.75 on the end route, as it already did on the stop route. Tests hold, in every language, that these three routes ask more than the default.
- « Je pense qu'on peut le faire maintenant. » moves from the idea route to the go-ahead route, in French and in the translations the other languages carried; a new idea example keeps each of their idea routes at 15 examples.
- Seven sentences of that session that took a wrong route become French cases that must stay neutral; the « on peut lancer ça maintenant » and « prépare ça maintenant » sentences become cases of the go-ahead route.

## Consequences

- On the 28 sentences, with the example moved: 12 right, none wrong, 16 neutral, against 14 right, 9 wrong and 5 neutral before. A wrong acknowledgement becomes the neutral one, which only says the message arrived.
- Four acknowledgements that fitted are lost to the neutral one, all between 0.5 and 0.6: « Oui, je veux bien en parler du modèle plus rapide… » (request, 0.52), « Alors je comprends pas pourquoi t'as parlé demain… » (request, 0.55), « Quand le pi démarre… le truc » (unfinished, 0.53) and « là tu m'as dit je suis là et ça n'est pas du tout approprié… » (no, 0.56). One is won: « prépare ça maintenant » now takes go-ahead at 0.62 rather than end.
- More than half of the sentences get the neutral acknowledgement. The lever to win them back is the examples: a sentence of the log that deserved a route is added to that route, rather than lowering the threshold.
- Every language takes the new default and the presence and end thresholds; their route tests, written by translation, still pass, but no real speech of those languages was measured.

### Limits

- 28 sentences of one speaker, in one evening, mostly long questions about the bridge itself: the sample is tiny and not representative of other topics.
- The rule was tuned on the same sentences it is judged on, so the figures above flatter it; the routes that fit each sentence were labelled by one reader.
- The thresholds are to be re-validated on the next sessions from the utterance events of the telemetry, comparing the route taken, its score and the acknowledgement played with what the speaker would have expected, before any further change.

## Alternatives considered

- **Keep 0.5 and only fix the examples**: each misfire had a different example behind it, and a long sentence finds a noisy match on some route whatever the examples.
- **A single higher threshold, 0.7 or 0.8**: removes the wrong picks only by making 71 % to 89 % of the sentences neutral, and loses the requests, go-aheads and problems that score between 0.6 and 0.7.
- **A margin over the second route**: on these sentences, it removes fewer wrong picks than the per-route thresholds and loses more good ones, since close routes such as yes and go-ahead often differ by less than 0.05.
- **Thresholds calibrated per route on a labelled corpus**, as [ADR-025](ADR-025-the-acknowledgements-follow-a-reviewed-set-of-principles.md) lists as future work: the right method, but it needs a corpus of hundreds of labelled sentences, which the utterance events will build over the coming sessions.
