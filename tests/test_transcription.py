from faster_whisper.transcribe import Segment

from pont_vocal.transcription import describe_segments


def segment(text, no_speech_prob, avg_logprob):
    return Segment(id=0, seek=0, start=0.0, end=1.0, text=text, tokens=[], avg_logprob=avg_logprob, compression_ratio=1.0, no_speech_prob=no_speech_prob, words=None, temperature=0.0)


def test_describe_segments_gives_the_scores_of_each_segment():
    segments = [segment(" Une transcription.", 0.42, -0.81), segment(" Merci.", 0.7, -1.2)]
    assert describe_segments(segments) == "« Une transcription. » sans parole 0.42, confiance -0.81 | « Merci. » sans parole 0.70, confiance -1.20"


def test_describe_segments_says_when_there_is_nothing():
    assert describe_segments([]) == "aucun segment"
