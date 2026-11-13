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

  Rule: A reply the speaker has not heard a sound of is not cut by their voice
    The voice is detected only after some speech, and the network delays the start of each
    sentence, so a reply can arrive after the speaker started talking but before their voice
    is detected. Nothing of it was heard, so it waits for the end of their turn instead of
    being dropped by their words.

    Scenario: A reply still being voiced is not cut when the speaker starts talking
      Given Claude is silent
      And Claude replied "I found three of them."
      When the speaker starts talking
      Then nothing happens

    Scenario: A voice ready while the speaker talks is not played over them
      Given Claude is silent
      And Claude replied "I found three of them."
      And the speaker started talking
      When Claude's voice for "I found three of them." is ready
      Then nothing happens

    Scenario: The unheard reply is spoken after the speaker's words, which are not an interruption
      Given Claude is silent
      And Claude replied "I found three of them."
      And the speaker started talking
      And Claude's voice for "I found three of them." was ready
      And the speaker said "Did you get my message?"
      When the speaker stays silent
      Then Claude hears "Did you get my message?"
      And Claude starts saying "I found three of them."

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

  Rule: A stop cuts Claude's voice, however short
    A single word such as « stop » holds too little voice to cut Claude off, so the words,
    once understood as a stop, cut the voice themselves and drop the rest of the reply.

    Scenario: A stop said over Claude's voice stops it
      Given Claude is replying "Let me look at your notes." then "I found three of them."
      When the speaker asks to stop with "Stop."
      Then Claude's voice stops when the stop is understood

    Scenario: A stop drops the rest of the reply
      Given Claude is replying "Let me look at your notes." then "I found three of them."
      When the speaker asks to stop with "Stop."
      Then Claude has nothing left to say

    Scenario: A stop that cut Claude's voice reaches Claude as an interruption
      Given Claude is replying "Let me look at your notes." then "I found three of them."
      And the speaker asked to stop with "Stop."
      When the speaker stays silent
      Then Claude hears "Stop." as an interruption

    Scenario: A stop that cut Claude's voice is acknowledged
      Given Claude is silent
      And Claude is saying "I found three of them."
      And the speaker asked to stop with "Stop."
      When the speaker stays silent
      Then the bridge acknowledges "Stop."

    Scenario: A stop after Claude's voice ended stops nothing
      Given Claude is silent
      And Claude said "I found three of them."
      When the speaker asks to stop with "Stop."
      Then Claude's voice is not stopped

    Scenario: A stop after the speaker cut Claude off does not stop the voice twice
      Given Claude is replying "Let me look at your notes." then "I found three of them."
      And the speaker cut Claude off
      When the speaker asks to stop with "Stop."
      Then Claude's voice is not stopped

    Scenario: A stop while Claude is silent reaches Claude plainly
      Given Claude is silent
      And the speaker asked to stop with "Stop."
      When the speaker stays silent
      Then Claude hears "Stop."

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

  Rule: Hold music plays while Claude works and stays silent
    Claude works from the words it was given, or from a turn Claude Code started on its own,
    until Claude Code tells the bridge it is done; Claude's own replies change nothing to it.

    Scenario: Words given to Claude bring the hold music after a wait
      Given Claude is silent
      And the speaker said "Where are we?"
      When the speaker stays silent
      Then the bridge waits for the hold music

    Scenario: A long wait while Claude works starts the hold music
      Given Claude is working on "Where are we?"
      When the wait goes on
      Then the hold music starts

    Scenario: Words given while Claude still talks wait for the end of its voice
      Given Claude is silent
      And Claude is saying "I found three of them."
      And the speaker said "And the logs too."
      When the speaker stays silent
      Then the hold music waits for the end of that voice

    Scenario: A reply of Claude at work waits for the end of its voice before the hold music
      Given Claude is working on "Where are we?"
      And Claude replied "Let me look at your notes."
      When Claude's voice for "Let me look at your notes." is ready
      Then the hold music waits for the end of that voice

    Scenario: A reply of several sentences waits for its last one
      Given Claude is working on "Where are we?"
      And Claude replied "I found it." then "Let me look at your notes."
      When Claude's voice for "I found it." is ready
      Then the bridge waits for no hold music

    Scenario: A reply once Claude is done leaves no room for music
      Given Claude is silent
      And Claude replied "Good."
      When Claude's voice for "Good." is ready
      Then the bridge waits for no hold music

    Scenario: A reply that comes before the end of the wait leaves no room for music
      Given Claude is working on "Where are we?"
      And Claude replied "Good."
      When the wait goes on
      Then nothing happens

    Scenario: Claude done before the end of the wait leaves no room for music
      Given Claude is working on "Where are we?"
      And Claude is done
      When the wait goes on
      Then nothing happens

    Scenario: A reply once Claude was done at work leaves no room for music
      Given Claude is working on "Where are we?"
      And Claude is done
      And Claude replied "Good."
      When Claude's voice for "Good." is ready
      Then the bridge waits for no hold music

    Scenario: Claude done stops the hold music
      Given the hold music plays
      When Claude is done
      Then the hold music stops

    Scenario: A turn Claude Code starts on its own brings the hold music after a wait
      Given Claude is silent
      When Claude starts working on its own
      Then the bridge waits for the hold music

    Scenario: A turn Claude Code starts on its own while Claude talks waits for the end of its voice
      Given Claude is silent
      And Claude is saying "I found three of them."
      When Claude starts working on its own
      Then the hold music waits for the end of that voice

    Scenario: A turn Claude Code starts on its own while the speaker talks brings no music yet
      Given the speaker is talking
      When Claude starts working on its own
      Then nothing happens

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

  Rule: The bridge announces the agents at work once nobody speaks
    The bridge says how many agents are at work each time one starts or finishes, from clips
    voiced at startup. It never cuts Claude's voice nor the speaker's: the announcement waits
    for the end of Claude's reply and of the speaker's words, and only the latest count is said.

    Scenario: An agent starting while all is silent is announced at once
      Given Claude is silent
      When an agent starts and 1 is at work
      Then the bridge announces 1 at work

    Scenario: An agent finishing is announced with the agents left at work
      Given Claude is silent
      When an agent finishes and 2 are left at work
      Then the bridge announces an agent finished with 2 left at work

    Scenario: An agent starting while Claude replies waits for its reply
      Given Claude is replying "Let me look at your notes." then "I found three of them."
      When an agent starts and 1 is at work
      Then the bridge announces nothing

    Scenario: The announcement follows the last sentence of Claude's reply
      Given Claude is replying "Let me look at your notes." then "I found three of them."
      And an agent started and 1 is at work
      When Claude's voice for "I found three of them." is ready
      Then the announcement follows Claude's voice

    Scenario: The announcement follows a reply that cannot be voiced
      Given Claude is replying "Let me look at your notes." then "I found three of them."
      And an agent started and 1 is at work
      When Claude's voice for "I found three of them." fails
      Then the bridge announces 1 at work

    Scenario: An agent starting while the speaker talks waits for their words
      Given the speaker is talking
      When an agent starts and 1 is at work
      Then nothing happens

    Scenario: An agent starting while the speaker begins some words waits for them
      Given Claude is silent
      And the speaker began some words
      When an agent starts and 1 is at work
      Then nothing happens

    Scenario: The announcement follows the acknowledgement of the speaker's words
      Given the speaker is talking
      And an agent started and 1 is at work
      And the speaker said "Where are we?"
      When the speaker stays silent
      Then the announcement follows the acknowledgement

    Scenario: The announcement is made after a sound too short to be heard
      Given Claude is silent
      And the speaker began some words
      And an agent started and 1 is at work
      When the speaker makes a sound too short to be heard
      Then the bridge announces 1 at work

    Scenario: The announcement is made after a noise
      Given the speaker is talking
      And an agent started and 1 is at work
      When the speaker only makes a noise
      Then the bridge announces 1 at work

    Scenario: Only the latest count is announced
      Given the speaker is talking
      And an agent started and 1 is at work
      And an agent started and 2 are at work
      And the speaker said "Where are we?"
      When the speaker stays silent
      Then the bridge announces 2 at work only

    Scenario: An announcement is made once
      Given Claude is silent
      And an agent started and 1 is at work
      When the speaker only makes a noise
      Then nothing happens

    Scenario: The announcement stops the hold music before it plays
      Given the hold music plays
      When an agent starts and 1 is at work
      Then the hold music stops before the announcement

    Scenario: The hold music comes back after the announcement
      Given the hold music plays
      When an agent starts and 1 is at work
      Then the bridge waits for the hold music from now on

    Scenario: An announcement after Claude's reply leaves the hold music to the end of its voice
      Given Claude is working on "Where are we?"
      And Claude replied "Good."
      And an agent started and 1 is at work
      When Claude's voice for "Good." is ready
      Then the hold music waits for the end of that voice

    Scenario: The hold music stopped by an announcement is not stopped again
      Given the hold music plays
      And an agent started and 1 is at work
      When Claude is done
      Then the hold music is not stopped again

    Scenario: An agent changing during the goodbye is not announced
      Given Claude is silent
      And Claude said goodbye with "See you tomorrow."
      And Claude's voice for "See you tomorrow." was ready
      When an agent finishes and 0 are left at work
      Then nothing happens

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
      And Claude is saying goodbye with "See you tomorrow."
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
