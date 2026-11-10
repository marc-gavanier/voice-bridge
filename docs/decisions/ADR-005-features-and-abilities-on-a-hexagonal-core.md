# ADR-005 — Features and abilities on a hexagonal core

**Date**: 2026-11-10
**Status**: accepted

## Context

The first bridge mixed everything in a few modules: one class held the Mumble connection, three threads with shared flags, voice detection, the interruption policy and the logs. It worked, but could not be reasoned about or tested without the network, and a reply arriving early or a synthesis failing could stop it silently.

Its author organises his TypeScript projects by feature and use case, on top of a hexagonal architecture, so that the folders say what the application does. In Python, the reference on ports and adapters, [Architecture Patterns with Python](https://www.cosmicpython.com/book/chapter_13_dependency_injection.html), wires dependencies explicitly in a composition root and treats dependency injection containers with suspicion.

## Decision

- **Features first.** `features/` holds `hearing`, `speaking`, `conversation` and `recording`. Each has a `domain` of pure functions on immutable values, `implementations` that talk to the outside world, and `abilities` that combine them. Shared technical code lives in `libraries/`, settings in `configuration/`.
- **Pure decisions.** The domain decides without side effects: utterance detection is a fold over audio frames, turn taking a state machine `step(state, event) -> (state, commands)`. The loops around them only receive events and carry out commands.
- **Ports as protocols.** An ability states what it needs with a `typing.Protocol`; tests pass fakes, never mocks.
- **Wiring in entry points.** The three commands in `entrypoints/` build the implementations and pass them in, with no container.
- **One concurrency model.** anyio task groups and memory streams, the model of the MCP SDK, replace threads, so a failing task raises instead of dying silently.
- **Contracts, not conventions.** Four import-linter contracts enforce the layout: entry points above configuration and features, features above libraries; features never import each other; abilities above implementations above the domain; and domains import nothing beyond the standard library.

## Consequences

- The interruption logic, the hardest part of the bridge, is tested as plain values.
- Features talk to each other only through the wiring, which keeps the entry point that assembles the voice loop longer than the others.
- Branch coverage is required at 100 %, except for the entry points and the network connection, which only wire tested parts.

## Alternatives considered

- **Architecture Patterns with Python's layout**, with top-level `domain`, `service_layer`, `adapters` and `entrypoints`. Consensual, but organised by technical layer: the folders would not say what the bridge does.
- **A dependency injection container**, such as svcs or dishka. Not needed at this size, and less idiomatic in Python than explicit wiring.
- **Pipecat**, the voice agent framework. It has no Mumble transport, and its pipeline calls the language model itself, whereas here Claude Code leads and the bridge is only its channel. Its models, Silero and Smart Turn, are used as components instead.
