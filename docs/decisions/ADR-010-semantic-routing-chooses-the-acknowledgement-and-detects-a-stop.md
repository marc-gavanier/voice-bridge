# ADR-010 — Semantic routing chooses the acknowledgement and detects a stop

**Date**: 2026-11-11
**Status**: accepted; its hook, renamed `voice-bridge-tool-hook`, also enforces [ADR-015](ADR-015-the-main-agent-delegates-in-voice-sessions.md)

## Context

The acknowledgement was chosen by regular expressions over the words, tried in order. They miss what they do not list: on 2026-11-11, « Est-ce que tu peux arrêter ? » matched the request rule, on « tu peux », and got « C'est parti. ». A stop asked by voice had no other effect than the instructions: Claude Code hands a channel message over only once the running tool call ends, and nothing in a channel can abort a turn, so a stop depended on Claude reading it and obeying (#7).

Recognising a stop from its meaning, without the word « stop », is the same problem as choosing the kind of acknowledgement: classing a short sentence by intent. The usual answer is semantic routing: each route holds example sentences, a sentence is embedded into a vector by a multilingual model, and it takes the route of its closest examples, if close enough.

A prototype measured it on 50 of the speaker's real sentences taken from the bridge's log, labelled by hand, 11 of them asking to stop:

| Model | Size | Right | False stops | Missed stops |
|---|---|---|---|---|
| `paraphrase-multilingual-MiniLM-L12-v2` | 0.22 GB | 34 to 35 / 50 | 2 to 3 | 1 |
| `paraphrase-multilingual-mpnet-base-v2` | 1 GB | 32 to 34 / 50 | 2 | 1 |
| `multilingual-e5-large` | 2.24 GB | 37 / 50 | 2 | 1 |

MiniLM embeds a sentence in 24 ms on the CPU. The false stops are the same for the three models: « Mais sans que ce soit nécessairement stop » and « Oui, ça s'est bien arrêté ». An embedding carries the topic of a sentence, not a negation nor the fact that a word is quoted. With a stricter threshold of 0.75 on the stop route alone, MiniLM recognised 9 stops out of 11 and made no false stop.

## Decision

- A new feature, `understanding`, classes each forwarded sentence. The routes, their example sentences (15 to 30 per route, many of them the speaker's own) and their acknowledgements are set per language in `language.py`; a sentence close to no route gets a neutral acknowledgement.
- The model is MiniLM, run with ONNX Runtime on the CPU, as Smart Turn is. Its ONNX build and tokenizer come from Hugging Face at a pinned revision (`Qdrant/paraphrase-multilingual-MiniLM-L12-v2-onnx-Q`, the build fastembed uses); the tokenizer runs with Hugging Face's `tokenizers`, already installed with faster-whisper, and the vectors are mean-pooled and normalised as in fastembed, whose output they match to 10⁻⁴. The example vectors are computed once, at startup.
- A sentence takes the closest route whose score reaches the route's threshold: `understanding.threshold`, 0.5, for every route but stop, which needs 0.75. The choice is a pure function of the scores, in the domain.
- Only the stop route asks to stop; the end-of-session route only chooses the acknowledgement, since saying goodbye does not interrupt work in progress. A sentence that asks to stop creates a flag file, `understanding.stop_flag`; the next forwarded sentence that does not ask to stop removes it.
- `voice-bridge-stop-hook`, a Claude Code `PreToolUse` hook registered by `claude-voice.sh` with `--settings`, refuses every tool but `mcp__voice__reply` and `TaskStop` while the flag exists, with a reason that tells Claude to stop and say what was stopped. The instructions say the same.

## Consequences

- An acknowledgement follows the meaning, and paraphrases and transcription errors derail it less than lists of words; but about a third of the sentences of the prototype still got another kind than the one a person would pick. The examples are the lever: a misread sentence of the log can be added to the right route.
- Stopping no longer depends on Claude obeying: from the next tool call, the hook refuses. A tool call already running still runs to its end, since a hook only sees calls before they start.
- A false stop refuses Claude's tools until the next sentence; a missed stop falls back on the instructions.
- The numbers come from 50 sentences, 11 of them stops: the thresholds are to be revised from the `understood … as … (score)` lines of the log.
- The hook runs `uv run` for every tool call, about 0.2 s.
- The first start needs network access to Hugging Face for the 220 MB model.

## Alternatives considered

- **Keep the regular expressions**: what failed; each new phrasing needs a new rule, and a stop phrased without a listed word is missed.
- **[semantic-router](https://github.com/aurelio-labs/semantic-router)**: the dedicated library, but it requires Python older than 3.14 and pulls the clients of Cohere, Mistral, OpenAI and Voyage.
- **[fastembed](https://github.com/qdrant/fastembed)**: runs the same ONNX model, but its current release pins `huggingface-hub` below 2.0, which the bridge already uses; uv then falls back to fastembed 0.1.1. Its pipeline is a tokenizer, an ONNX session and a mean pooling, which the bridge already has the libraries for.
- **Larger models**: mpnet (1 GB) and multilingual-e5-large (2.24 GB) were measured; they are not better on the negation and quotation traps, and are five to ten times heavier.
- **Haiku as a classifier**: understands negation, but adds a network round trip and a cost to every sentence, before the acknowledgement that must come within half a second.
- **The word « stop » alone**: misses « laisse tomber » or « ne fais pas ça », and stops on « je n'ai pas dit stop ».
