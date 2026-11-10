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
