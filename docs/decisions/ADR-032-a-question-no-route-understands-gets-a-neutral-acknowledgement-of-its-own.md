# ADR-032 — A question no route understands gets a neutral acknowledgement of its own

**Date**: 2026-11-15
**Status**: accepted, revises the neutral pool of [ADR-025](ADR-025-the-acknowledgements-follow-a-reviewed-set-of-principles.md); to re-validate on the next sessions

## Context

[ADR-030](ADR-030-the-acknowledgement-thresholds-sit-above-the-noise-of-unrelated-sentences.md) raised the thresholds so that a sentence close to no route gets the neutral acknowledgement rather than a wrong one. On the 28 sentences it was tuned on, 16 became neutral, and most of the session's sentences were long questions about the bridge itself.

[ADR-025](ADR-025-the-acknowledgements-follow-a-reviewed-set-of-principles.md) asks the neutral pool to hold formulas that fit any message, and gave « Je vois. » as one. Two of its French sentences do not: « Ah, OK. » and « Je vois. » react to news, and answer a question as if it were information. At 01:52 on 2026-11-15, « Les nouveaux seuils sont-ils activés ? » passed no route, the closest being below 0.6, and got « Ah, OK. ». The speaker expected « Attends, je vérifie ça » or « Je regarde ». The other neutral sentences, such as « Reçu. » or « C'est noté. », fit a question better but still say nothing of what comes next.

A question is the one kind of sentence that the transcription marks without any model: Whisper ends it with a question mark.

## Decision

- The sentences of the neutral pools that react to news leave them, in every language: « Ah, OK. » and « Je vois. » in French; "Ah, okay.", "I see." and "Okay, I see." in English; "Ah, okay.", "Ah, verstehe.", "Ich verstehe." and "Verstehe." in German; "Ah, vale." and "Ya veo." in Spanish; "Ah, ok.", "Ah, capisco." and "Capisco." in Italian; "Ah, oké." and "Ah, ik snap het." in Dutch; "Ah, entendi.", "Ah, tá." and "Estou vendo." in Portuguese; the two sentences opened by "آه" in Arabic and the two opened by "अच्छा" in Hindi. They stay in the routes where they fit, such as « Ah, OK. » in the no route.
- Each language file gains `neutral_question_acknowledgements`, sentences that fit any question because they only say the bridge looks into it. French: « Voyons. », « Je regarde. », « Laisse-moi voir. », « Je vérifie. », « Un instant, je regarde. », « Attends, je vérifie ça. ». The eight other languages carry six sentences that look or check, most of them already in their question route.
- When no route passes its threshold and the words, trimmed, end with `?`, the full-width `？` or the Arabic `؟`, the acknowledgement is drawn from that pool; otherwise from the neutral pool. Hindi writes `?`. A route that passes always wins over the question mark. The same sentence still never plays twice in a row, across every pool.
- The speaking ability's domain decides, from the route understood and the words; the voice entry point wires it.
- The utterance event of a sentence that passed no route carries `voice_bridge.route.fallback`, `neutral` or `neutral_question`.

## Consequences

- « Les nouveaux seuils sont-ils activés ? » and the three French questions that the tests kept neutral now get the question pool.
- Every route still comes first: a question that passes the question, request or presence route gets that route's sentence, as before.
- The neutral pools lose two to four sentences each and keep 16 or more, so a repeat stays unlikely.
- The calibration of ADR-030 can count, from the utterance events, how many sentences fell back on each pool.
- The sentences of the eight other languages were written by translation and are unreviewed by native speakers.

### Limits

- Whisper does not always put the question mark: a question said with a falling tone, or cut by a pause, may come without one and get the neutral pool, which still fits it. A sentence that ends with a question mark but is not one, such as a rhetorical question, gets « Je regarde. », which commits to little.
- The rule was drawn from one sentence of one evening; how often it fires, and whether its sentences fit, is to be checked on the next sessions from the `voice_bridge.route.fallback` attribute.

## Alternatives considered

- **A route for questions in general, at a lower threshold**: the question route exists, and the sentences that missed it are long questions about anything, which score in the noise ADR-030 described; a lower threshold brings back the wrong picks it removed.
- **Only removing the sentences that react to news**: leaves « Reçu. » for a question, which fits but says nothing of what comes next, while the question mark already tells what is needed.
- **Detecting a question from its words**, such as « est-ce que » or an inversion: depends on each language's grammar, while the question mark is already written by Whisper in all nine.
