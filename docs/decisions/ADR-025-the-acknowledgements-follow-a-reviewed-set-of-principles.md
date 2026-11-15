# ADR-025 — The acknowledgements follow a reviewed set of principles

**Date**: 2026-11-14
**Status**: accepted, revises the routes of [ADR-010](ADR-010-semantic-routing-chooses-the-acknowledgement-and-detects-a-stop.md)

## Context

[ADR-010](ADR-010-semantic-routing-chooses-the-acknowledgement-and-detects-a-stop.md) set twelve routes, each with four to eight acknowledgements written without a review. Marc, the speaker, reviewed every French one by ear and found:

- sentences that commit to more than what was understood: « Parfait, c'est noté. » or « D'accord, on y va. » after a restart, « Très bien, on laisse. » after a no, « Continue. » or « Et donc ? » after an unfinished sentence, which sound like impatience;
- a thanks route that also held the compliments, so that « bravo, tu as bien travaillé » got « Avec plaisir. », which answers a thank-you, not praise;
- a restarted route whose acknowledgements did not say what the speaker wants to know after a restart: that the bridge hears again, the question of the presence route;
- an idea route that answered « J'ai une idée… », said before the idea, and a complete idea with the same sentences, « Intéressant. » before anything was said; a yes route that answered « vas-y, lance » and « oui, c'est bien » alike;
- « on laisse » and « on s'arrête là », quoted in a review, coming close to the stop route;
- « Je vérifie. », which belongs to the problem and the question routes, heard twice in a row, since the bridge remembered the last sentence of each route only;
- one fixed greeting, « Je t'écoute. », heard at every start.

## Decision

The acknowledgements follow these principles, in every language:

- **Prudence**: an acknowledgement never commits to more than the route is sure of. In doubt, the neutral pool answers, with formulas that only say the message arrived (« Reçu. », « C'est noté. », « Je vois. »), which fit any message.
- **One formula per acknowledgement**, except a patience formula paired with an action, such as « Un instant, je regarde. » or « Noté, je cherche. », which tells both that the bridge heard and what comes next.
- **A sentence may belong to several routes**, such as « Je vérifie. » for a problem and for a question, or « Je t'écoute. » for presence, an unfinished sentence and an idea being announced. The bridge remembers the last sentence it played, whatever the route, and never plays it twice in a row.
- **The greeting is drawn from the presence route**, marked `greets` in the language file, since it answers the same need as « tu m'entends ? ». The acknowledgements start from it, so the first one never repeats it.

The routes become fourteen, in the same order in every language, which a test holds:

| Route | Change | Example of the speaker | French acknowledgements |
|---|---|---|---|
| `stop` | kept, threshold 0.75 | « Stop, est-ce que tu peux arrêter ? » | « J'arrête immédiatement. »… |
| `end` | « on s'arrête là » added | « On s'arrête là pour aujourd'hui. » | « À bientôt. », « On s'arrête là. »… |
| `unfinished` | kept | « Donc… » | « Oui ? », « Prends ton temps. »… |
| `presence` | merged with `restarted`; greets | « Tu m'entends ? », « J'ai redémarré. » | « Je suis là. », « Je t'entends. »… |
| `thanks` | compliments moved out | « Merci beaucoup. » | « Avec plaisir. », « Je t'en prie. »… |
| `compliment` | new | « Bravo, tu as bien travaillé. » | « Merci, ça fait plaisir. »… |
| `problem` | kept | « Ça a coupé. » | « Un instant, je vérifie. »… |
| `request` | kept | « Lance les tests. » | « Je m'en occupe. »… |
| `question` | kept | « Pourquoi ça ne marche pas ? » | « Bonne question. »… |
| `idea_coming` | split from `idea` | « J'ai une idée… » | « Je t'écoute. » |
| `idea` | kept for a complete idea | « On pourrait utiliser un autre outil. » | « Ça se tient. »… |
| `no` | « on laisse ça comme ça » added | « Non, ce n'est pas ça. » | « Pas de souci. », « Je corrige. »… |
| `go_ahead` | split from `yes` | « Oui, fais-le. » | « C'est parti. », « Allons-y. »… |
| `yes` | kept for a yes that only agrees; « on laisse comme ça » added | « Oui, c'est bien. » | « Parfait. », « Entendu. »… |

« OK. » stays out of every pool, although the review listed it: Voxtral derails on it, and the test that keeps it out still holds.

The other eight languages follow the same routes and principles. Their acknowledgements are written as a speaker of the language would say them in a casual exchange, not translated word for word from French, in about as many sentences per route:

- the familiar register of each language, as French uses « tu »: « du », « tú », « tu », « je », « você », « तुम », and the masculine address of Arabic;
- the gender of the voice each language is spoken with: female everywhere but in Arabic, so « Obrigada », « Sono tutta orecchi » or « मैं सुन रही हूँ »;
- one variety per language: the Spanish of Spain, the Portuguese of Brazil, the Dutch of the Netherlands, spoken Hindi with the English words it uses, such as « चेक करती हूँ », and the light Modern Standard Arabic understood across the Arab world, with common spoken turns such as « تمام » or « يلا بنا »;
- the idioms of the language for the backchannels, thanks and stops, such as « Wird gemacht. », « Komt voor elkaar. », « Imagina. » or « Figurati. », rather than the French ones, and none that commits to an outcome, such as « Komt goed. », or says the work is done, such as « تم. ».

No native speaker has reviewed them yet: they were written on 2026-11-15 without one, and checked only against the router and the tests.

## Consequences

- An acknowledgement that does not fit costs less: the neutral pool and the prudent sentences fit more messages than « Parfait, c'est noté. » did.
- A praise gets a thank-you, a thank-you gets « Avec plaisir. », and a yes that launches an action gets « C'est parti. » rather than « Parfait. ».
- The greeting changes at each start, and is never followed by the same sentence.
- « On laisse comme ça » and « on s'arrête là » now land on the yes and end routes, by nearer examples, not by a rule; a sentence close to both, such as « Bon, on laisse ça. », still scores as high on stop as on yes, so the stop threshold is still what keeps a false stop away.
- Splitting idea and yes puts close examples on neighbouring routes: the margin between `yes` and `go_ahead`, or `idea_coming` and `idea`, is often below 0.1. A wrong pick between them is mild, since both sides are prudent.

### Future work, not decided here

- **Tiered thresholds per route**: each sentence gets a confidence level, and the thresholds are calibrated on a corpus of the speaker's labelled sentences, so that a route answers with a committing sentence only when it is sure, and with a prudent one otherwise.
- **Finer question routes**, asking for a verification, an explanation or an opinion, if the corpus shows they can be told apart.
- **A stop that blocks at once with an undo window**: about ten seconds during which « annule » lifts it.
- **Detecting a message not addressed to the bridge**: no acknowledgement, and the message forwarded with a flag.
- **A review by native speakers** of the eight languages other than French, by ear, as Marc did for French, with their own sentences for the route tests.
- **Calibration from the OpenTelemetry utterance events** of the `feat/utterance-events` branch, which record each utterance, the route taken, the three closest routes with their scores and the acknowledgement played.

## Alternatives considered

- **Negative examples on the stop route**, sentences that must not stop: the language file has no such field, and the router would need a rule to subtract them. Positive examples on the right routes do the same with the existing mechanism; calibrated thresholds may replace both.
- **Keep the last sentence per route**: what let « Je vérifie. » play twice in a row.
- **Keep a fixed greeting**: heard at every start, and possibly followed by the same sentence as the first acknowledgement.
- **Keep thanks and compliments together**: one pool cannot answer both, since « Avec plaisir. » answers a thank-you and « Merci. » answers a praise.
