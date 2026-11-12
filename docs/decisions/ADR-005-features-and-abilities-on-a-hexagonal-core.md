# ADR-005 — Features and abilities on a hexagonal core

**Date**: 2026-11-10, revised 2026-11-12
**Status**: accepted

## Context

The first bridge mixed everything in a few modules: one class held the Mumble connection, three threads with shared flags, voice detection, the interruption policy and the logs. It worked, but could not be reasoned about or tested without the network, and a reply arriving early or a synthesis failing could stop it silently.

Its author organises his TypeScript projects by feature and use case, on top of a hexagonal architecture, so that the folders say what the application does. In la Coop, a feature holds a `domain` and an `implementation` shared by its abilities, and each ability is a vertical slice under `abilities/<ability>/` with its own `domain` and `implementation`. In Python, the reference on ports and adapters, [Architecture Patterns with Python](https://www.cosmicpython.com/book/chapter_13_dependency_injection.html), wires dependencies explicitly in a composition root and treats dependency injection containers with suspicion.

The first version of this decision translated abilities as a layer above the feature's implementations, and checked the layout with four import-linter contracts. #34 found that they let through what the decision forbade: a layers contract allowed every ability to import any implementation, and "domains are pure Python" was a deny list of packages, so a package missing from it passed.

## Decision

- **Features first.** `features/` holds `hearing`, `speaking`, `conversation`, `understanding` and `recording`. Shared technical code lives in `libraries/`, settings in `configuration/`, and the commands in `entrypoints/`.
- **Abilities are vertical slices.** A feature holds a `domain` and an `implementation` shared by its abilities, and each ability lives in `abilities/<ability>/` with a `domain` for its ports and pure logic, when it has some, and an `implementation` for its shell and its own adapters. An adapter used by one ability alone, whether its shell imports it or the entry points pass it in to fill one of its ports, lives in that ability's `implementation`; only an adapter used by several abilities goes to the feature's `implementation`, which no feature needs today. Every package's `__init__.py` stays empty: no package re-exports an ability, and entry points import each ability's module directly.
- **Functional core, imperative shell.** Business decisions belong in a domain, as pure functions on immutable values: utterance detection is a fold over audio frames, turn taking a state machine `step(state, event) -> (state, commands)`. The shell in the ability's `implementation` only receives events, runs the anyio loop and carries out commands.
- **Ports as protocols.** An ability states what it needs with a `typing.Protocol` in its `domain`; tests pass fakes typed with these ports, never mocks.
- **Wiring in entry points.** Entry points build the implementations and pass them in, with no container.
- **One concurrency model.** anyio task groups and memory streams, the model of the MCP SDK, replace threads, so a failing task raises instead of dying silently.
- **Seven rules on imports:**
  1. Features never import each other; only `voice_bridge.entrypoints` assembles them.
  2. An ability never imports another ability, of its feature or of another.
  3. Feature-level code, a feature's `domain` and `implementation`, never imports an ability. Abilities may import feature-level code.
  4. A feature's `domain` imports only the standard library and the language extensions allowed in `LANGUAGE_EXTENSIONS`.
  5. An ability's `domain` imports only what rule 4 allows, plus its own feature's `domain`.
  6. An ability's `implementation` may import its own ability, its feature's `domain` and `implementation`, `voice_bridge.libraries` and outside packages; never another ability or another feature.
  7. Only entry points import an ability's `implementation`; a feature's `implementation` is imported only by entry points and by the implementations of its abilities.
- **Language extensions are an explicit allow list.** A language extension is a library that a domain uses as part of the language, as Effect is in TypeScript. `LANGUAGE_EXTENSIONS` in `tests/architecture/test_allowed_imports.py` lists their top-level module names; it is empty. Adding one is a change to that constant, reviewed in its own pull request with its reason in the commit.
- **Rules checked by tools, not conventions.** import-linter checks what its built-in contracts express: rules 1 and 2 as `independence` contracts with wildcards, rule 3 as a `forbidden` contract, rule 7 as two `protected` contracts, and a `layers` contract keeps libraries below features and configuration. Because the `protected` contracts refuse any other importer, a feature's or an ability's `__init__.py` cannot re-export an ability. Rules 4, 5 and 6 are allow lists, which import-linter cannot express: pytest checks them on the import graph built by grimp, the library under import-linter, and prints each forbidden `importer -> imported` pair.

## Consequences

- The interruption logic, the hardest part of the bridge, is tested as plain values.
- Features talk to each other only through the wiring, which keeps the entry point that assembles the voice loop longer than the others.
- A new package used by a domain fails the tests until it is added to the allow list, and a new import between abilities or features fails the contracts.
- Each adapter sits next to the only ability that uses it, so the folders say which ability depends on Silero, Whisper or the speech API. An ability's shell may still import its own adapters and the libraries directly; replacing such an adapter means introducing a port in the ability's domain first.
- Some decisions still sit in shells, such as `advance` in `listen` and `record`; moving them into a domain is a later change, guided by the rule above.
- Logger names follow module paths, so the log lines of an ability carry its full path.
- Branch coverage is required at 100 %, except for the entry points and the network connection, which only wire tested parts.

## Alternatives considered

- **Architecture Patterns with Python's layout**, with top-level `domain`, `service_layer`, `adapters` and `entrypoints`. Consensual, but organised by technical layer: the folders would not say what the bridge does.
- **Abilities as a layer above implementations**, the first version of this decision. It gave an ability no place for its ports, and its contracts could not tell an ability's own adapter from another's.
- **Only import-linter**, combining `forbidden`, `independence` and `layers` contracts into allow lists. A `forbidden` contract lists what is refused, so an unlisted package passes; expressing "anything but the standard library" would need the list of every installed package, kept by hand.
- **A Python tool closer to dependency-cruiser**, declaring the allowed dependencies of each module. It would add a tool and a configuration format, while grimp is already installed with import-linter and the three allow lists fit in one test file.
- **A dependency injection container**, such as svcs or dishka. Not needed at this size, and less idiomatic in Python than explicit wiring.
- **Pipecat**, the voice agent framework. It has no Mumble transport, and its pipeline calls the language model itself, whereas here Claude Code leads and the bridge is only its channel. Its models, Silero and Smart Turn, are used as components instead.
