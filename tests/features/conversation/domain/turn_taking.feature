Feature: Turn taking
  The speaker and the assistant share one voice channel: the speaker may cut the assistant off at any time,
  and what interrupted decides what happens to the rest of the assistant's reply.

  Rule: Speaking over the assistant cuts its voice

    Scenario: Speaking while the assistant talks stops its voice
      Given the assistant is replying "Let me look at your notes." then "I found three of them."
      When the speaker starts talking
      Then the assistant's voice stops

    Scenario: Speaking while the assistant is silent changes nothing
      Given the assistant is silent
      When the speaker starts talking
      Then nothing happens

  Rule: A reply the speaker has not heard a sound of is not cut by their voice
    The voice is detected only after some speech, and the network delays the start of each
    sentence, so a reply can arrive after the speaker started talking but before their voice
    is detected. Nothing of it was heard, so it waits for the end of their turn instead of
    being dropped by their words.

    Scenario: A reply still being voiced is not cut when the speaker starts talking
      Given the assistant is silent
      And the assistant replied "I found three of them."
      When the speaker starts talking
      Then nothing happens

    Scenario: A voice ready while the speaker talks is not played over them
      Given the assistant is silent
      And the assistant replied "I found three of them."
      And the speaker started talking
      When the assistant's voice for "I found three of them." is ready
      Then the assistant's voice does not play

    Scenario: A voice ready while the speaker talks abandons its synthesis
      Given the assistant is silent
      And the assistant replied "I found three of them."
      And the speaker started talking
      When the first piece of the assistant's voice for "I found three of them." is ready
      Then the synthesis under way is abandoned

    Scenario: The unheard reply is spoken after the speaker's words, which are not an interruption
      Given the assistant is silent
      And the assistant replied "I found three of them."
      And the speaker started talking
      And the assistant's voice for "I found three of them." was ready
      And the speaker said "Did you get my message?"
      When the speaker stays silent
      Then the assistant hears "Did you get my message?"
      And the assistant starts saying "I found three of them."

  Rule: A reply that arrives while the speaker talks waits for the end of their turn

    Scenario: A reply arriving while the speaker talks stays silent
      Given the speaker is talking
      When the assistant replies "I found three of them."
      Then nothing happens

    Scenario: The speaker talking on does not cut a reply they have not heard
      Given the speaker is talking
      And the assistant replied "I found three of them."
      When the speaker keeps talking
      Then nothing happens

    Scenario: A reply arriving while the speaker's words wait stays silent
      Given the assistant is silent
      And the speaker said "Where are we?"
      When the assistant replies "I found three of them."
      Then nothing happens

    Scenario: The held reply still waits while the speaker may go on
      Given the speaker is talking
      And the assistant replied "I found three of them."
      When the speaker says "And the logs too."
      Then the assistant says nothing yet

    Scenario: The held reply is spoken once the speaker stays silent after their words
      Given the speaker is talking
      And the assistant replied "I found three of them."
      And the speaker said "And the logs too."
      When the speaker stays silent
      Then the assistant starts saying "I found three of them."
      And the assistant hears "And the logs too."

    Scenario: The held reply is spoken after a noise
      Given the speaker is talking
      And the assistant replied "I found three of them."
      When the speaker only makes a noise
      Then the assistant starts saying "I found three of them."

  Rule: A noise resumes the reply it cut

    Scenario: A cough after an interruption resumes what was left unsaid
      Given the assistant is replying "Let me look at your notes." then "I found three of them."
      And the speaker cut the assistant off
      When the speaker only makes a noise
      Then the assistant still has to say "Let me look at your notes." then "I found three of them."

    Scenario: A noise without an interruption is ignored
      Given the assistant is silent
      When the speaker only makes a noise
      Then nothing happens

    Scenario: A sound too short to be heard does not resume the reply
      Given the assistant is replying "Let me look at your notes." then "I found three of them."
      And the speaker cut the assistant off
      When the speaker makes a sound too short to be heard
      Then nothing happens

    Scenario: Words still being transcribed after a short sound reach the assistant as an interruption
      Given the assistant is replying "Let me look at your notes." then "I found three of them."
      And the speaker began some words
      And the speaker cut the assistant off
      And the speaker began some words
      And the speaker made a sound too short to be heard
      And the speaker said "Wait, I have a question."
      When the speaker stays silent
      Then the assistant hears "Wait, I have a question." as an interruption

  Rule: Words drop the reply they cut and reach the assistant as an interruption

    Scenario: Words after an interruption drop the rest of the reply
      Given the assistant is replying "Let me look at your notes." then "I found three of them."
      And the speaker cut the assistant off
      When the speaker says "Wait, I have a question."
      Then the assistant has nothing left to say

    Scenario: Words after an interruption tell the assistant it was cut off
      Given the assistant is replying "Let me look at your notes." then "I found three of them."
      And the speaker cut the assistant off
      And the speaker said "Wait, I have a question."
      When the speaker stays silent
      Then the assistant hears "Wait, I have a question." as an interruption

    Scenario: Words without an interruption reach the assistant plainly
      Given the assistant is silent
      And the speaker said "Where are we?"
      When the speaker stays silent
      Then the assistant hears "Where are we?"

    Scenario: Only the words that cut the assistant off reach it as an interruption
      Given the assistant is replying "Let me look at your notes." then "I found three of them."
      And the speaker cut the assistant off
      And the speaker said "Wait, I have a question."
      And the speaker stayed silent
      And the speaker said "And the logs too."
      When the speaker stays silent
      Then the assistant hears "And the logs too."

  Rule: A stop cuts the assistant's voice, however short
    A single word such as « stop » holds too little voice to cut the assistant off, so the words,
    once understood as a stop, cut the voice themselves and drop the rest of the reply.

    Scenario: A stop said over the assistant's voice stops it
      Given the assistant is replying "Let me look at your notes." then "I found three of them."
      When the speaker asks to stop with "Stop."
      Then the assistant's voice stops when the stop is understood

    Scenario: A stop drops the rest of the reply
      Given the assistant is replying "Let me look at your notes." then "I found three of them."
      When the speaker asks to stop with "Stop."
      Then the assistant has nothing left to say

    Scenario: A stop that cut the assistant's voice reaches the assistant as an interruption
      Given the assistant is replying "Let me look at your notes." then "I found three of them."
      And the speaker asked to stop with "Stop."
      When the speaker stays silent
      Then the assistant hears "Stop." as an interruption

    Scenario: A stop that cut the assistant's voice is acknowledged
      Given the assistant is silent
      And the assistant is saying "I found three of them."
      And the speaker asked to stop with "Stop."
      When the speaker stays silent
      Then the bridge acknowledges "Stop."

    Scenario: A stop after the assistant's voice ended stops nothing
      Given the assistant is silent
      And the assistant said "I found three of them."
      When the speaker asks to stop with "Stop."
      Then the assistant's voice is not stopped

    Scenario: A stop after the speaker cut the assistant off does not stop the voice twice
      Given the assistant is replying "Let me look at your notes." then "I found three of them."
      And the speaker cut the assistant off
      When the speaker asks to stop with "Stop."
      Then the assistant's voice is not stopped

    Scenario: A stop while the assistant is silent reaches the assistant plainly
      Given the assistant is silent
      And the speaker asked to stop with "Stop."
      When the speaker stays silent
      Then the assistant hears "Stop."

  Rule: Words reach the assistant once the speaker stays silent, joined into one message
    A speaker who thinks aloud pauses mid-sentence: words wait for a silence long enough
    that the speaker has finished, so that the assistant neither hears nor answers half a thought.

    Scenario: Words do not reach the assistant at once
      Given the assistant is silent
      When the speaker says "Where are we?"
      Then the assistant hears nothing yet

    Scenario: Words said in pieces reach the assistant as one message
      Given the assistant is silent
      And the speaker said "I would like..."
      And the speaker said "a ticket for the logs."
      When the speaker stays silent
      Then the assistant hears "I would like... a ticket for the logs."

    Scenario: A speaker who goes on after a pause holds their words back
      Given the assistant is silent
      And the speaker said "I would like..."
      And the speaker went on
      When the speaker stays silent
      Then the assistant hears nothing yet

    Scenario: A speaker who goes on before their words are transcribed holds them back
      Given the assistant is silent
      And the speaker began some words
      And the speaker went on
      And the speaker said "I would like..."
      When the speaker stays silent
      Then the assistant hears nothing yet

    Scenario: Only the silence after the last words lets them reach the assistant
      Given the assistant is silent
      And the speaker said "I would like..."
      And the speaker said "a ticket for the logs."
      When the silence after the first words ends
      Then the assistant hears nothing yet

    Scenario: A noise after a pause does not hold the words back
      Given the assistant is silent
      And the speaker said "I would like a ticket."
      And the speaker went on
      And the speaker only made a noise
      When the speaker stays silent
      Then the assistant hears "I would like a ticket."

    Scenario: A sound too short to be heard after a pause does not hold the words back
      Given the assistant is silent
      And the speaker said "I would like a ticket."
      And the speaker went on
      And the speaker made a sound too short to be heard
      When the speaker stays silent
      Then the assistant hears "I would like a ticket."

    Scenario: Words already sent are not sent again
      Given the assistant is silent
      And the speaker said "I would like a ticket."
      And the speaker stayed silent
      And the speaker said "For the logs."
      When the speaker stays silent
      Then the assistant hears "For the logs."

  Rule: Words are acknowledged once the speaker stays silent, after what they said

    Scenario: Words are acknowledged after the speaker's words
      Given the assistant is silent
      And the speaker said "Where are we?"
      When the speaker stays silent
      Then the bridge acknowledges "Where are we?"

    Scenario: Words are not acknowledged at once
      Given the assistant is silent
      When the speaker says "The repository is clean."
      Then the bridge acknowledges nothing

    Scenario: A speaker who goes on after a pause is not acknowledged
      Given the assistant is silent
      And the speaker said "The repository is clean."
      And the speaker went on
      When the speaker stays silent
      Then the bridge acknowledges nothing

    Scenario: A reply that comes first makes the acknowledgement useless
      Given the assistant is silent
      And the speaker said "The repository is clean."
      And the assistant replied "Good."
      When the speaker stays silent
      Then the bridge acknowledges nothing

    Scenario: Only the silence after the last words acknowledges them
      Given the assistant is silent
      And the speaker said "The repository is clean."
      And the speaker said "And the logs too."
      When the silence after the first words ends
      Then the bridge acknowledges nothing

    Scenario: A noise is not acknowledged
      Given the assistant is replying "Let me look at your notes." then "I found three of them."
      And the speaker cut the assistant off
      When the speaker only makes a noise
      Then the bridge acknowledges nothing

  Rule: Only one acknowledgement is played until the assistant replies

    Scenario: Words already acknowledged are not acknowledged again before the assistant replies
      Given the assistant is silent
      And the speaker said "The repository is clean."
      And the speaker stayed silent
      And the speaker said "And the logs too."
      When the speaker stays silent
      Then the bridge acknowledges nothing

    Scenario: A reply lets the next words be acknowledged
      Given the assistant is silent
      And the speaker said "The repository is clean."
      And the speaker stayed silent
      And the assistant said "Good."
      And the speaker said "And the logs too."
      When the speaker stays silent
      Then the bridge acknowledges "And the logs too."

    Scenario: The assistant learns that the words it hears will be acknowledged
      Given the assistant is silent
      And the speaker said "Where are we?"
      When the speaker stays silent
      Then the assistant hears "Where are we?" with an acknowledgement to come

    Scenario: The assistant learns that words heard after an acknowledgement will not be acknowledged again
      Given the assistant is silent
      And the speaker said "The repository is clean."
      And the speaker stayed silent
      And the speaker said "And the logs too."
      When the speaker stays silent
      Then the assistant hears "And the logs too." with no acknowledgement to come

  Rule: Words are not acknowledged while the assistant is already replying

    Scenario: Words said while a reply is being voiced are not acknowledged
      Given the assistant is silent
      And the assistant replied "Good."
      And the speaker said "And the logs too."
      When the speaker stays silent
      Then the bridge acknowledges nothing

    Scenario: Words said while the assistant talks are not acknowledged
      Given the assistant is silent
      And the assistant is saying "Let me look at your notes."
      And the speaker said "And the logs too."
      When the speaker stays silent
      Then the bridge acknowledges nothing

  Rule: Hold music plays while the assistant works and stays silent
    The assistant works from the words it was given, or from a turn it started on its own,
    until the assistant tells the bridge it is done; its own replies change nothing to it.
    Words that the acknowledgement fully answers, such as "Can you hear me?", give the assistant
    nothing to do: they bring no music, unless they were said in pieces, over the assistant's voice,
    or while the assistant was already at work.

    Scenario: Words given to the assistant bring the hold music after a wait
      Given the assistant is silent
      And the speaker said "Where are we?"
      When the speaker stays silent
      Then the bridge waits for the hold music

    Scenario: A long wait while the assistant works starts the hold music
      Given the assistant is working on "Where are we?"
      When the wait goes on
      Then the hold music starts

    Scenario: Words the acknowledgement answers bring no hold music
      Given the assistant is silent
      And the speaker said "Can you hear me?", which its acknowledgement answers
      When the speaker stays silent
      Then the bridge waits for no hold music

    Scenario: Words the acknowledgement answers keep the hold music of an assistant at work
      Given the assistant started working on its own
      And the speaker said "Can you hear me?", which its acknowledgement answers
      When the speaker stays silent
      Then the bridge waits for the hold music

    Scenario: Words the acknowledgement would answer, said while the assistant talks, bring the hold music
      Given the assistant is silent
      And the assistant is saying "I found three of them."
      And the speaker said "Can you hear me?", which its acknowledgement answers
      When the speaker stays silent
      Then the hold music waits for the end of that voice

    Scenario: Words the acknowledgement answers, said over the assistant, bring the hold music
      Given the assistant is replying "Let me look at your notes." then "I found three of them."
      And the speaker cut the assistant off
      And the speaker said "Can you hear me?", which its acknowledgement answers
      When the speaker stays silent
      Then the bridge waits for the hold music

    Scenario: Words said in pieces bring the hold music even when the last piece is answered
      Given the assistant is silent
      And the speaker said "The logs."
      And the speaker said "Can you hear me?", which its acknowledgement answers
      When the speaker stays silent
      Then the bridge waits for the hold music

    Scenario: Words given while the assistant still talks wait for the end of its voice
      Given the assistant is silent
      And the assistant is saying "I found three of them."
      And the speaker said "And the logs too."
      When the speaker stays silent
      Then the hold music waits for the end of that voice

    Scenario: A reply of the assistant at work waits for the end of its voice before the hold music
      Given the assistant is working on "Where are we?"
      And the assistant replied "Let me look at your notes."
      When the assistant's voice for "Let me look at your notes." is ready
      Then the hold music waits for the end of that voice

    Scenario: A reply of several sentences waits for its last one
      Given the assistant is working on "Where are we?"
      And the assistant replied "I found it." then "Let me look at your notes."
      When the assistant's voice for "I found it." is ready
      Then the bridge waits for no hold music

    Scenario: A reply once the assistant is done leaves no room for music
      Given the assistant is silent
      And the assistant replied "Good."
      When the assistant's voice for "Good." is ready
      Then the bridge waits for no hold music

    Scenario: A reply that comes before the end of the wait leaves no room for music
      Given the assistant is working on "Where are we?"
      And the assistant replied "Good."
      When the wait goes on
      Then nothing happens

    Scenario: An assistant done before the end of the wait leaves no room for music
      Given the assistant is working on "Where are we?"
      And the assistant is done
      When the wait goes on
      Then nothing happens

    Scenario: A reply once the assistant was done at work leaves no room for music
      Given the assistant is working on "Where are we?"
      And the assistant is done
      And the assistant replied "Good."
      When the assistant's voice for "Good." is ready
      Then the bridge waits for no hold music

    Scenario: An assistant done stops the hold music
      Given the hold music plays
      When the assistant is done
      Then the hold music stops

    Scenario: A turn the assistant starts on its own brings the hold music after a wait
      Given the assistant is silent
      When the assistant starts working on its own
      Then the bridge waits for the hold music

    Scenario: A turn the assistant starts on its own while it talks waits for the end of its voice
      Given the assistant is silent
      And the assistant is saying "I found three of them."
      When the assistant starts working on its own
      Then the hold music waits for the end of that voice

    Scenario: A turn the assistant starts on its own while the speaker talks brings no music yet
      Given the speaker is talking
      When the assistant starts working on its own
      Then nothing happens

    Scenario: The first sentence of the reply stops the hold music
      Given the hold music plays
      And the assistant replied "Good."
      When the assistant's voice for "Good." is ready
      Then the hold music stops before the assistant speaks

    Scenario: A reply that cannot be voiced stops the hold music
      Given the hold music plays
      And the assistant replied "Good."
      When the assistant's voice for "Good." fails
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

  Rule: The bridge says that the assistant does not answer when it never has
    The assistant may wait on its screen, before its first turn, for a confirmation nobody can
    give without a screen, such as Claude Code's warning about development channels. It then never
    tells the bridge anything, and the hold music would play forever. Once the assistant has told
    the bridge it works or is done, words it does not take at once are only queued behind its turn.

    Scenario: Words given to an assistant never heard from wait for its answer
      Given the assistant has not answered since the bridge started
      And the speaker said "Where are we?"
      When the speaker stays silent
      Then the bridge waits for the assistant to answer

    Scenario: Words given to an assistant heard from do not wait for its answer
      Given the assistant has not answered since the bridge started
      And the assistant told the bridge it works
      And the speaker said "Where are we?"
      When the speaker stays silent
      Then the bridge does not wait for the assistant to answer

    Scenario: Words given to an assistant done before do not wait for its answer
      Given the assistant has not answered since the bridge started
      And the assistant is done
      And the speaker said "Where are we?"
      When the speaker stays silent
      Then the bridge does not wait for the assistant to answer

    Scenario: An assistant that never answers is said to wait on its screen
      Given the speaker's words reached an assistant that never answered
      When the wait for an answer goes on
      Then the bridge says that the assistant does not answer

    Scenario: An assistant that never answers no longer counts as working
      Given the speaker's words reached an assistant that never answered
      When the wait for an answer goes on
      Then the assistant no longer counts as working

    Scenario: An assistant that starts working before the end of the wait is not said to wait
      Given the speaker's words reached an assistant that never answered
      And the assistant told the bridge it works
      When the wait for an answer goes on
      Then nothing happens

    Scenario: An assistant done before the end of the wait is not said to wait
      Given the speaker's words reached an assistant that never answered
      And the assistant is done
      When the wait for an answer goes on
      Then nothing happens

    Scenario: Only the wait for the latest words counts
      Given the speaker's words reached an assistant that never answered
      And the speaker said "And the logs too."
      And the speaker stayed silent
      When the wait for the earlier words goes on
      Then nothing happens

    Scenario: The hold music does not start after the assistant was said not to answer
      Given the speaker's words reached an assistant that never answered, with a long wait for the music
      And the wait for an answer went on
      When the wait goes on
      Then nothing happens

  Rule: A recording the assistant plays takes its turn like a sentence of its reply
    The assistant can have the bridge play an audio file to the speaker. It is heard after what it
    still has to say, stops the hold music as a sentence does, and speaking over it cuts it
    like the assistant's voice.

    Scenario: A recording played while the assistant is silent is made ready at once
      Given the assistant is silent
      When the assistant plays the recording "sample.wav"
      Then the assistant starts saying the recording "sample.wav"

    Scenario: A recording waits for the sentences still to say
      Given the assistant is silent
      And the assistant replied "Here it is." then "Listen."
      When the assistant plays the recording "sample.wav"
      Then the assistant still has to say "Here it is." and "Listen." before the recording "sample.wav"

    Scenario: A ready recording stops the hold music before it plays
      Given the hold music plays
      And the assistant played the recording "sample.wav"
      When the recording "sample.wav" is ready
      Then the hold music stops before the assistant speaks

    Scenario: Speaking over a recording stops it
      Given the assistant is playing the recording "sample.wav"
      When the speaker starts talking
      Then the assistant's voice stops

    Scenario: A noise plays the cut recording again
      Given the assistant is playing the recording "sample.wav"
      And the speaker cut the assistant off
      When the speaker only makes a noise
      Then the assistant starts saying the recording "sample.wav"

  Rule: The bridge announces the agents at work once nobody speaks
    The bridge says how many agents are at work each time their count changes to two or more,
    from clips voiced at startup. A single agent at work, or none, is never announced: the hold
    music already tells that the assistant works. It never cuts the assistant's voice nor the speaker's: the
    announcement waits for the end of the assistant's reply and of the speaker's words, and only the
    latest count is said.

    Scenario: A second agent starting while all is silent is announced at once
      Given the assistant is silent
      When an agent starts and 2 are at work
      Then the bridge announces 2 at work

    Scenario: An agent finishing is announced with the agents left at work
      Given the assistant is silent
      When an agent finishes and 2 are left at work
      Then the bridge announces 2 at work

    Scenario: A single agent at work is not announced
      Given the assistant is silent
      When an agent starts and 1 is at work
      Then the bridge announces nothing

    Scenario: An agent finishing with a single one left is not announced
      Given the assistant is silent
      When an agent finishes and 1 is left at work
      Then the bridge announces nothing

    Scenario: The last agent finishing is not announced
      Given the assistant is silent
      When an agent finishes and 0 are left at work
      Then the bridge announces nothing

    Scenario: An agent resumed is announced with the agents at work
      Given the assistant is silent
      When an agent is resumed and 2 are at work
      Then the bridge announces 2 at work

    Scenario: An agent paused and resumed while the speaker talks is announced once
      Given the speaker is talking
      And an agent finished and 2 are left at work
      And an agent was resumed and 3 are at work
      And the speaker said "Where are we?"
      When the speaker stays silent
      Then the bridge announces 3 at work only

    Scenario: A count falling below two drops the announcement still waiting
      Given the speaker is talking
      And an agent started and 2 are at work
      And an agent finished and 1 is left at work
      And the speaker said "Where are we?"
      When the speaker stays silent
      Then the bridge announces nothing

    Scenario: An agent starting while the assistant replies waits for its reply
      Given the assistant is replying "Let me look at your notes." then "I found three of them."
      When an agent starts and 2 are at work
      Then the bridge announces nothing

    Scenario: The announcement follows the last sentence of the assistant's reply
      Given the assistant is replying "Let me look at your notes." then "I found three of them."
      And an agent started and 2 are at work
      When the assistant's voice for "I found three of them." is ready
      Then the announcement follows the assistant's voice

    Scenario: The announcement follows a reply that cannot be voiced
      Given the assistant is replying "Let me look at your notes." then "I found three of them."
      And an agent started and 2 are at work
      When the assistant's voice for "I found three of them." fails
      Then the bridge announces 2 at work

    Scenario: An agent starting while the speaker talks waits for their words
      Given the speaker is talking
      When an agent starts and 2 are at work
      Then nothing happens

    Scenario: An agent starting while the speaker begins some words waits for them
      Given the assistant is silent
      And the speaker began some words
      When an agent starts and 2 are at work
      Then nothing happens

    Scenario: The announcement follows the acknowledgement of the speaker's words
      Given the speaker is talking
      And an agent started and 2 are at work
      And the speaker said "Where are we?"
      When the speaker stays silent
      Then the announcement follows the acknowledgement

    Scenario: The announcement is made after a sound too short to be heard
      Given the assistant is silent
      And the speaker began some words
      And an agent started and 2 are at work
      When the speaker makes a sound too short to be heard
      Then the bridge announces 2 at work

    Scenario: The announcement is made after a noise
      Given the speaker is talking
      And an agent started and 2 are at work
      When the speaker only makes a noise
      Then the bridge announces 2 at work

    Scenario: Only the latest count is announced
      Given the speaker is talking
      And an agent started and 2 are at work
      And an agent started and 3 are at work
      And the speaker said "Where are we?"
      When the speaker stays silent
      Then the bridge announces 3 at work only

    Scenario: An announcement is made once
      Given the assistant is silent
      And an agent started and 2 are at work
      When the speaker only makes a noise
      Then nothing happens

    Scenario: The announcement stops the hold music before it plays
      Given the hold music plays
      When an agent starts and 2 are at work
      Then the hold music stops before the announcement

    Scenario: The hold music comes back after the announcement
      Given the hold music plays
      When an agent starts and 2 are at work
      Then the bridge waits for the hold music from now on

    Scenario: An announcement after the assistant's reply leaves the hold music to the end of its voice
      Given the assistant is working on "Where are we?"
      And the assistant replied "Good."
      And an agent started and 2 are at work
      When the assistant's voice for "Good." is ready
      Then the hold music waits for the end of that voice

    Scenario: The hold music stopped by an announcement is not stopped again
      Given the hold music plays
      And an agent started and 2 are at work
      When the assistant is done
      Then the hold music is not stopped again

    Scenario: An agent changing during the goodbye is not announced
      Given the assistant is silent
      And the assistant said goodbye with "See you tomorrow."
      And the assistant's voice for "See you tomorrow." was ready
      When an agent starts and 2 are at work
      Then nothing happens

  Rule: A goodbye ends the session once the speaker has heard it

    Scenario: The goodbye ends the session when its voice ends
      Given the assistant is silent
      And the assistant said goodbye with "See you tomorrow."
      When the assistant's voice for "See you tomorrow." is ready
      Then the bridge leaves when that voice ends

    Scenario: The goodbye waits for the sentences before it
      Given the assistant is silent
      And the assistant replied "It is pushed."
      And the assistant said goodbye with "See you tomorrow."
      When the assistant's voice for "It is pushed." is ready
      Then the bridge does not leave yet
      And the assistant starts saying "See you tomorrow."

    Scenario: A goodbye that cannot be voiced still ends the session
      Given the assistant is silent
      And the assistant said goodbye with "See you tomorrow."
      When the assistant's voice for "See you tomorrow." fails
      Then the bridge leaves at once

    Scenario: Words said over the goodbye keep the session going
      Given the assistant is silent
      And the assistant is saying goodbye with "See you tomorrow."
      And the speaker cut the assistant off
      And the speaker said "Wait, one more thing."
      When the speaker stays silent
      Then the assistant hears "Wait, one more thing." as an interruption
      And the session goes on

    Scenario: A noise over the goodbye still ends the session
      Given the assistant is silent
      And the assistant said goodbye with "See you tomorrow."
      And the speaker cut the assistant off
      And the speaker only made a noise
      When the assistant's voice for "See you tomorrow." is ready
      Then the bridge leaves when that voice ends

  Rule: The assistant's voice plays as it arrives
    The speech server streams the voice of a sentence in pieces. The first piece plays at once,
    and the next sentence is synthesized once the whole voice of this one has arrived, so only one
    sentence is synthesized at a time. A synthesis whose voice is no longer wanted is abandoned,
    so the server stops voicing it.

    Scenario: The first piece of a voice plays before the rest arrives
      Given the assistant is silent
      And the assistant replied "I found three of them."
      When the first piece of the assistant's voice for "I found three of them." is ready
      Then the assistant's voice plays

    Scenario: The next sentence waits for the whole voice of the one before
      Given the assistant is silent
      And the assistant replied "Let me look at your notes." then "I found three of them."
      When the first piece of the assistant's voice for "Let me look at your notes." is ready
      Then the assistant says nothing yet

    Scenario: The next sentence is synthesized once the voice of the one before has arrived
      Given the assistant is silent
      And the assistant replied "Let me look at your notes." then "I found three of them."
      And the first piece of the assistant's voice for "Let me look at your notes." was ready
      When the rest of the assistant's voice for "Let me look at your notes." arrives
      Then the assistant starts saying "I found three of them."

    Scenario: Speaking over a voice still arriving abandons its synthesis
      Given the assistant is silent
      And the assistant replied "I found three of them."
      And the first piece of the assistant's voice for "I found three of them." was ready
      When the speaker starts talking
      Then the synthesis under way is abandoned

    Scenario: Speaking over a voice still arriving stops it
      Given the assistant is silent
      And the assistant replied "I found three of them."
      And the first piece of the assistant's voice for "I found three of them." was ready
      When the speaker starts talking
      Then the assistant's voice stops

    Scenario: A noise resumes a sentence whose voice was still arriving
      Given the assistant is silent
      And the assistant replied "I found three of them."
      And the first piece of the assistant's voice for "I found three of them." was ready
      And the speaker cut the assistant off
      When the speaker only makes a noise
      Then the assistant starts saying "I found three of them."

    Scenario: Speaking while the assistant is silent abandons no synthesis
      Given the assistant is silent
      When the speaker starts talking
      Then no synthesis is abandoned

    Scenario: A voice that breaks off moves on to the next sentence
      Given the assistant is silent
      And the assistant replied "Let me look at your notes." then "I found three of them."
      And the first piece of the assistant's voice for "Let me look at your notes." was ready
      When the assistant's voice for "Let me look at your notes." fails
      Then the assistant starts saying "I found three of them."

  Rule: The bridge warns once when the assistant's voice cannot be made
    A speech server that restarts during a session fails every sentence until it is back, and
    the speaker would only hear silence. The first failure warns them with a sentence recorded
    in advance; the next failures do not repeat it, until a voice plays again.

    Scenario: A reply that cannot be voiced warns that the voice is lost
      Given the assistant is silent
      And the assistant replied "Let me look at your notes." then "I found three of them."
      When the assistant's voice for "Let me look at your notes." fails
      Then the bridge warns that the voice is lost

    Scenario: The warning comes before the next sentence
      Given the assistant is silent
      And the assistant replied "Let me look at your notes." then "I found three of them."
      When the assistant's voice for "Let me look at your notes." fails
      Then the warning comes before the assistant starts saying "I found three of them."

    Scenario: The next failure does not warn again
      Given the assistant is silent
      And the assistant replied "Let me look at your notes." then "I found three of them."
      And the assistant's voice for "Let me look at your notes." failed
      When the assistant's voice for "I found three of them." fails
      Then the bridge does not warn that the voice is lost

    Scenario: The next failure still moves on to the next sentence
      Given the assistant is silent
      And the assistant replied "Let me look at your notes." then "I found three of them."
      And the assistant replied "Shall I open them?"
      And the assistant's voice for "Let me look at your notes." failed
      When the assistant's voice for "I found three of them." fails
      Then the assistant starts saying "Shall I open them?"

    Scenario: A voice that plays again warns again at the next failure
      Given the assistant is silent
      And the assistant replied "Let me look at your notes." then "I found three of them."
      And the assistant's voice for "Let me look at your notes." failed
      And the first piece of the assistant's voice for "I found three of them." was ready
      When the assistant's voice for "I found three of them." fails
      Then the bridge warns that the voice is lost

    Scenario: A failure for an older sentence does not warn
      Given the assistant is silent
      And the assistant replied "Let me look at your notes." then "I found three of them."
      And the assistant's voice for "Let me look at your notes." was ready
      When the voice of an older sentence fails
      Then nothing happens
