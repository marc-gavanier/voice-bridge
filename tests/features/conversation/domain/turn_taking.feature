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

    Scenario: A reply arriving while the speaker's words wait stays silent
      Given Claude is silent
      And the speaker said "Where are we?"
      When Claude replies "I found three of them."
      Then nothing happens

    Scenario: The held reply still waits while the speaker may go on
      Given the speaker is talking
      And Claude replied "I found three of them."
      When the speaker says "And the logs too."
      Then Claude says nothing yet

    Scenario: The held reply is spoken once the speaker stays silent after their words
      Given the speaker is talking
      And Claude replied "I found three of them."
      And the speaker said "And the logs too."
      When the speaker stays silent
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

    Scenario: A sound too short to be heard does not resume the reply
      Given Claude is replying "Let me look at your notes." then "I found three of them."
      And the speaker cut Claude off
      When the speaker makes a sound too short to be heard
      Then nothing happens

    Scenario: Words still being transcribed after a short sound reach Claude as an interruption
      Given Claude is replying "Let me look at your notes." then "I found three of them."
      And the speaker began some words
      And the speaker cut Claude off
      And the speaker began some words
      And the speaker made a sound too short to be heard
      And the speaker said "Wait, I have a question."
      When the speaker stays silent
      Then Claude hears "Wait, I have a question." as an interruption

  Rule: Words drop the reply they cut and reach Claude as an interruption

    Scenario: Words after an interruption drop the rest of the reply
      Given Claude is replying "Let me look at your notes." then "I found three of them."
      And the speaker cut Claude off
      When the speaker says "Wait, I have a question."
      Then Claude has nothing left to say

    Scenario: Words after an interruption tell Claude it was cut off
      Given Claude is replying "Let me look at your notes." then "I found three of them."
      And the speaker cut Claude off
      And the speaker said "Wait, I have a question."
      When the speaker stays silent
      Then Claude hears "Wait, I have a question." as an interruption

    Scenario: Words without an interruption reach Claude plainly
      Given Claude is silent
      And the speaker said "Where are we?"
      When the speaker stays silent
      Then Claude hears "Where are we?"

    Scenario: Only the words that cut Claude off reach it as an interruption
      Given Claude is replying "Let me look at your notes." then "I found three of them."
      And the speaker cut Claude off
      And the speaker said "Wait, I have a question."
      And the speaker stayed silent
      And the speaker said "And the logs too."
      When the speaker stays silent
      Then Claude hears "And the logs too."

  Rule: Words reach Claude once the speaker stays silent, joined into one message
    A speaker who thinks aloud pauses mid-sentence: words wait for a silence long enough
    that the speaker has finished, so that Claude neither hears nor answers half a thought.

    Scenario: Words do not reach Claude at once
      Given Claude is silent
      When the speaker says "Where are we?"
      Then Claude hears nothing yet

    Scenario: Words said in pieces reach Claude as one message
      Given Claude is silent
      And the speaker said "I would like..."
      And the speaker said "a ticket for the logs."
      When the speaker stays silent
      Then Claude hears "I would like... a ticket for the logs."

    Scenario: A speaker who goes on after a pause holds their words back
      Given Claude is silent
      And the speaker said "I would like..."
      And the speaker went on
      When the speaker stays silent
      Then Claude hears nothing yet

    Scenario: A speaker who goes on before their words are transcribed holds them back
      Given Claude is silent
      And the speaker began some words
      And the speaker went on
      And the speaker said "I would like..."
      When the speaker stays silent
      Then Claude hears nothing yet

    Scenario: Only the silence after the last words lets them reach Claude
      Given Claude is silent
      And the speaker said "I would like..."
      And the speaker said "a ticket for the logs."
      When the silence after the first words ends
      Then Claude hears nothing yet

    Scenario: A noise after a pause does not hold the words back
      Given Claude is silent
      And the speaker said "I would like a ticket."
      And the speaker went on
      And the speaker only made a noise
      When the speaker stays silent
      Then Claude hears "I would like a ticket."

    Scenario: A sound too short to be heard after a pause does not hold the words back
      Given Claude is silent
      And the speaker said "I would like a ticket."
      And the speaker went on
      And the speaker made a sound too short to be heard
      When the speaker stays silent
      Then Claude hears "I would like a ticket."

    Scenario: Words already sent are not sent again
      Given Claude is silent
      And the speaker said "I would like a ticket."
      And the speaker stayed silent
      And the speaker said "For the logs."
      When the speaker stays silent
      Then Claude hears "For the logs."

  Rule: Words are acknowledged once the speaker stays silent, after what they said

    Scenario: Words are acknowledged after the speaker's words
      Given Claude is silent
      And the speaker said "Where are we?"
      When the speaker stays silent
      Then the bridge acknowledges "Where are we?"

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
      And Claude said "Good."
      And the speaker said "And the logs too."
      When the speaker stays silent
      Then the bridge acknowledges "And the logs too."

    Scenario: Claude learns that the words it hears will be acknowledged
      Given Claude is silent
      And the speaker said "Where are we?"
      When the speaker stays silent
      Then Claude hears "Where are we?" with an acknowledgement to come

    Scenario: Claude learns that words heard after an acknowledgement will not be acknowledged again
      Given Claude is silent
      And the speaker said "The repository is clean."
      And the speaker stayed silent
      And the speaker said "And the logs too."
      When the speaker stays silent
      Then Claude hears "And the logs too." with no acknowledgement to come

  Rule: Words are not acknowledged while Claude is already replying

    Scenario: Words said while a reply is being voiced are not acknowledged
      Given Claude is silent
      And Claude replied "Good."
      And the speaker said "And the logs too."
      When the speaker stays silent
      Then the bridge acknowledges nothing

    Scenario: Words said while Claude talks are not acknowledged
      Given Claude is silent
      And Claude is saying "Let me look at your notes."
      And the speaker said "And the logs too."
      When the speaker stays silent
      Then the bridge acknowledges nothing

  Rule: Hold music plays while Claude works on what it announced

    Scenario: An announced work waits for the end of the announcement before the hold music
      Given Claude is silent
      And Claude announced "Let me look at your notes."
      When Claude's voice for "Let me look at your notes." is ready
      Then the hold music waits for the end of that voice

    Scenario: A long wait after an announcement starts the hold music
      Given Claude announced work with "Let me look at your notes."
      When the wait goes on
      Then the hold music starts

    Scenario: An announcement of several sentences waits for its last one
      Given Claude is silent
      And Claude announced "I found it." then "Let me look at your notes."
      When Claude's voice for "I found it." is ready
      Then the bridge waits for no hold music

    Scenario: A reply that announces no work leaves no room for music
      Given Claude is silent
      And Claude replied "Good."
      When Claude's voice for "Good." is ready
      Then the bridge waits for no hold music

    Scenario: A reply that comes before the end of the wait leaves no room for music
      Given Claude announced work with "Let me look at your notes."
      And Claude replied "Good."
      When the wait goes on
      Then nothing happens

    Scenario: The acknowledgement brings no hold music
      Given Claude is silent
      And the speaker said "The repository is clean."
      When the speaker stays silent
      Then the bridge waits for no hold music

    Scenario: The first sentence of the reply stops the hold music
      Given the hold music plays
      And Claude replied "Good."
      When Claude's voice for "Good." is ready
      Then the hold music stops before Claude speaks

    Scenario: A reply that cannot be voiced stops the hold music
      Given the hold music plays
      And Claude replied "Good."
      When Claude's voice for "Good." fails
      Then the hold music stops

    Scenario: Speaking stops the hold music
      Given the hold music plays
      When the speaker starts talking
      Then the hold music stops

    Scenario: Words said while waiting bring the music back after a new wait
      Given the hold music plays
      And the speaker cut in
      And the speaker said "And the logs too."
      And the speaker stayed silent
      When the wait goes on
      Then the hold music starts

  Rule: A goodbye ends the session once the speaker has heard it

    Scenario: The goodbye ends the session when its voice ends
      Given Claude is silent
      And Claude said goodbye with "See you tomorrow."
      When Claude's voice for "See you tomorrow." is ready
      Then the bridge leaves when that voice ends

    Scenario: The goodbye waits for the sentences before it
      Given Claude is silent
      And Claude replied "It is pushed."
      And Claude said goodbye with "See you tomorrow."
      When Claude's voice for "It is pushed." is ready
      Then the bridge does not leave yet
      And Claude starts saying "See you tomorrow."

    Scenario: A goodbye that cannot be voiced still ends the session
      Given Claude is silent
      And Claude said goodbye with "See you tomorrow."
      When Claude's voice for "See you tomorrow." fails
      Then the bridge leaves at once

    Scenario: Words said over the goodbye keep the session going
      Given Claude is silent
      And Claude said goodbye with "See you tomorrow."
      And the speaker cut Claude off
      And the speaker said "Wait, one more thing."
      When the speaker stays silent
      Then Claude hears "Wait, one more thing." as an interruption
      And the session goes on

    Scenario: A noise over the goodbye still ends the session
      Given Claude is silent
      And Claude said goodbye with "See you tomorrow."
      And the speaker cut Claude off
      And the speaker only made a noise
      When Claude's voice for "See you tomorrow." is ready
      Then the bridge leaves when that voice ends
