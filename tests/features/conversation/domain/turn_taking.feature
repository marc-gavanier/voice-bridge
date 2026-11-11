Feature: Turn taking
  The speaker and Claude share one voice channel: the speaker may cut Claude off at any time,
  and what interrupted decides what happens to the rest of Claude's reply.

  Rule: Speaking over Claude cuts its voice

    Scenario: Speaking while Claude talks stops its voice
      Given Claude is replying "Let me look at your notes." then "I found three of them."
      When the speaker starts talking
      Then Claude's voice stops

    Scenario: Speaking while Claude is silent changes nothing
      Given Claude is silent
      When the speaker starts talking
      Then nothing happens

  Rule: A reply that arrives while the speaker talks waits for the end of their turn

    Scenario: A reply arriving while the speaker talks stays silent
      Given the speaker is talking
      When Claude replies "I found three of them."
      Then nothing happens

    Scenario: The speaker talking on does not cut a reply they have not heard
      Given the speaker is talking
      And Claude replied "I found three of them."
      When the speaker keeps talking
      Then nothing happens

    Scenario: The held reply is spoken once the speaker's words are heard
      Given the speaker is talking
      And Claude replied "I found three of them."
      When the speaker says "And the logs too."
      Then Claude starts saying "I found three of them."
      And Claude hears "And the logs too."

    Scenario: The held reply is spoken after a noise
      Given the speaker is talking
      And Claude replied "I found three of them."
      When the speaker only makes a noise
      Then Claude starts saying "I found three of them."

  Rule: A noise resumes the reply it cut

    Scenario: A cough after an interruption resumes what was left unsaid
      Given Claude is replying "Let me look at your notes." then "I found three of them."
      And the speaker cut Claude off
      When the speaker only makes a noise
      Then Claude still has to say "Let me look at your notes." then "I found three of them."

    Scenario: A noise without an interruption is ignored
      Given Claude is silent
      When the speaker only makes a noise
      Then nothing happens

  Rule: Words drop the reply they cut and reach Claude as an interruption

    Scenario: Words after an interruption drop the rest of the reply
      Given Claude is replying "Let me look at your notes." then "I found three of them."
      And the speaker cut Claude off
      When the speaker says "Wait, I have a question."
      Then Claude has nothing left to say

    Scenario: Words after an interruption tell Claude it was cut off
      Given Claude is replying "Let me look at your notes." then "I found three of them."
      And the speaker cut Claude off
      When the speaker says "Wait, I have a question."
      Then Claude hears "Wait, I have a question." as an interruption

    Scenario: Words without an interruption reach Claude plainly
      Given Claude is silent
      When the speaker says "Where are we?"
      Then Claude hears "Where are we?"

  Rule: Words are acknowledged once the speaker stays silent, as a question or as a statement

    Scenario: A question is acknowledged as a question
      Given Claude is silent
      And the speaker said "Where are we?"
      When the speaker stays silent
      Then the bridge acknowledges a question

    Scenario: A statement is acknowledged as a statement
      Given Claude is silent
      And the speaker said "The repository is clean."
      When the speaker stays silent
      Then the bridge acknowledges a statement

    Scenario: Words are not acknowledged at once
      Given Claude is silent
      When the speaker says "The repository is clean."
      Then the bridge acknowledges nothing

    Scenario: A speaker who goes on after a pause is not acknowledged
      Given Claude is silent
      And the speaker said "The repository is clean."
      And the speaker went on
      When the speaker stays silent
      Then the bridge acknowledges nothing

    Scenario: A reply that comes first makes the acknowledgement useless
      Given Claude is silent
      And the speaker said "The repository is clean."
      And Claude replied "Good."
      When the speaker stays silent
      Then the bridge acknowledges nothing

    Scenario: Only the silence after the last words acknowledges them
      Given Claude is silent
      And the speaker said "The repository is clean."
      And the speaker said "And the logs too."
      When the silence after the first words ends
      Then the bridge acknowledges nothing

    Scenario: A noise is not acknowledged
      Given Claude is replying "Let me look at your notes." then "I found three of them."
      And the speaker cut Claude off
      When the speaker only makes a noise
      Then the bridge acknowledges nothing

  Rule: Only one acknowledgement is played until Claude replies

    Scenario: Words already acknowledged are not acknowledged again before Claude replies
      Given Claude is silent
      And the speaker said "The repository is clean."
      And the speaker stayed silent
      And the speaker said "And the logs too."
      When the speaker stays silent
      Then the bridge acknowledges nothing

    Scenario: A reply lets the next words be acknowledged
      Given Claude is silent
      And the speaker said "The repository is clean."
      And the speaker stayed silent
      And Claude replied "Good."
      And the speaker said "And the logs too."
      When the speaker stays silent
      Then the bridge acknowledges a statement
