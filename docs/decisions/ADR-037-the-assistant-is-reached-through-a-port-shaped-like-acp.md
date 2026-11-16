# ADR-037 — The assistant is reached through a port shaped like ACP

**Date**: 2026-11-16
**Status**: accepted

## Context

[ADR-034](ADR-034-every-brick-of-the-voice-chain-is-swappable-behind-a-port.md) puts the assistant second in its order of work: a neutral port of our own, whose notions and messages follow the [Agent Client Protocol](https://agentclientprotocol.com/protocol/overview) (ACP), with Claude Code as its first adapter (#79). Until then, the conversation called a port named `Claude`, shaped like Claude Code's channel notification, and left by a callable that sent `SIGTERM` to Claude Code's process. The board of agents read the models of Claude Code's activity hook and its `subagent` task type, the stop rule in *understanding* parsed the `PreToolUse` event and wrote its denial, and the tool hook's entry point listed Claude Code's tool names. The rehearsal faked the assistant with a bare function.

ACP's specification, checked on 2026-11-16, has a client prompt an agent with `session/prompt`, which is answered with a stop reason (`end_turn`, `max_tokens`, `max_turn_requests`, `refusal`, `cancelled`); interrupt it with `session/cancel`; end a session with `session/close`. While the turn runs, the agent sends `session/update` notifications: `agent_message_chunk`, `tool_call` with an id, a title, a kind and a status, `tool_call_update` with the fields that changed, `plan`, among others. ACP has no notion of a subagent, of an agent ending the session, or of an update outside a prompt turn.

## Decision

The conversation reaches the assistant through the `Assistant` port in `hold_conversation/domain/ports.py`, whose messages live in `hold_conversation/domain/assistant.py`:

- **`prompt(Prompt)`**, after `session/prompt`: the words heard, whether they cut the assistant off, and the acknowledgement the speaker hears. The interruption is told with the next prompt rather than as a `session/cancel`, because the speaker cuts the assistant's voice, not its work.
- **`close()`**, after `session/close`, once a goodbye has been said.
- **Session updates** streamed back to the bridge:
  - `AgentMessageChunk`, after `agent_message_chunk`: a reply, with a clip to play, or `closing` when the assistant asks to end the session, which ACP lacks.
  - `TurnStarted` and `TurnEnded`, for a prompt turn and its end. `TurnEnded` says whether work is left in the background and lists the agents still running, when the assistant knows them; it carries no stop reason, since nothing in the bridge acts on one yet.
  - `ToolCall`, `ToolCallUpdate` and `ToolCallCompleted`, after `tool_call` and `tool_call_update`: an agent at work is a tool call, titled with its type, updated with its latest action, and completed with its last message.

The **Claude Code adapter** keeps everything Claude Code's: the MCP channel and its experimental `claude/channel` capability, turning a prompt into a channel notification and the channel's tools into message chunks; the activity hook, whose wire format between hook and bridge is unchanged and whose events become session updates as the bridge hears them, keeping the rule that only a `subagent` task is an agent; the tool hook's answer, with Claude Code's tool names and its `PreToolUse` denial, asking *understanding* only whether a tool is refused after a stop; and the process, ended with `SIGTERM` on close. The channel's entry point listens to the hooks beside the conversation, so the voice wiring no longer knows the activity socket.

The **echo** of the rehearsal is a second adapter: it answers each prompt with its own words, and closing it ends nothing.

Turn taking's events are named after the assistant, `AssistantBusy` and `AssistantIdle`, and its scenarios speak of the assistant.

## Consequences

- Another assistant plugs in as one more adapter in `hold_conversation/implementation`, built by an entry point, with no change to turn taking, the board or the voice wiring.
- An **ACP adapter** would map almost one to one: `prompt` to `session/prompt`, its response to `TurnEnded`, `close` to `session/close`, `agent_message_chunk`, `tool_call` and `tool_call_update` to the updates of the same names. It would also invert the processes, the bridge spawning the agent; and it needs answers ACP does not give yet: how an agent pushes a message outside a turn, ends the session, or tells its subagents.
- `TurnEnded` and the tool calls carry the list of running agents because Claude Code tells it at each stop; an assistant that does not leaves it out, and the board keeps what it knows.
- The voice instructions, the tool descriptions in the language files, the `claude` settings section and the `claude` span of the traces still name Claude Code. The settings move by port in their own unit, as ADR-034 orders; the span name stays, so as not to break what reads the traces.
- The README's sequence diagrams and guide still speak of Claude, the only assistant a person talks to today.

## Alternatives considered

- **ACP's own messages as the port**, JSON-RPC included. ADR-034 already set it aside: it ties the core to a protocol that is not stable and that Claude Code does not speak.
- **An interruption as `cancel()`**. The speaker who cuts the voice does not ask the assistant to drop its work, and Claude Code's channel has no cancel: it would have been a method no adapter honours.
- **A stop reason on `TurnEnded`**. Claude Code's hooks do not tell an error from a stop once they reach the bridge, and nothing reads it; it can be added with the first adapter that has one.
- **Subagents as a notion of their own.** ACP has none, and tool calls already carry an id, a title, updates and an end, which is all the board needs.
- **Sending the neutral updates over the activity socket.** It would change the wire between hook and bridge, so a hook and a bridge from two checkouts could not talk during an upgrade, for no gain: the conversion is the adapter's own business.
