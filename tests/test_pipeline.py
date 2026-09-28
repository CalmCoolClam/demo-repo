from togi_clipper.config import Config
from togi_clipper.highlights import clean_clips
from togi_clipper.render import ass_time, build_ass, slug
from togi_clipper.transcribe import timestamped_text, words_between

TRANSCRIPT = {
    "video": "v.mp4",
    "duration": 120.0,
    "segments": [
        {"start": 10.0, "end": 12.0, "text": "I bought a Lambo",
         "words": [{"start": 10.0, "end": 10.3, "word": "I"}, {"start": 10.3, "end": 10.8, "word": "bought"},
                   {"start": 10.8, "end": 11.0, "word": "a"}, {"start": 11.0, "end": 11.8, "word": "Lambo"}]},
        {"start": 70.5, "end": 71.0, "text": "later", "words": [{"start": 70.5, "end": 71.0, "word": "later"}]},
    ],
}


def clip(start, end, score):
    return {"start": start, "end": end, "virality_score": score, "hook_title": "t", "why": "w", "captions": []}


def test_clean_clips_filters_and_orders():
    cfg = Config(clips_per_video=2)
    clips = [
        clip(0, 5, 10),        # too short
        clip(10, 40, 7),
        clip(30, 60, 9),       # best, overlaps the one above
        clip(100, 140, 8),     # clamped to 120 -> 20s, ok
        clip(0, 200, 6),       # too long
    ]
    out = clean_clips(clips, 120.0, cfg)
    assert [(c["start"], c["end"]) for c in out] == [(30, 60), (100, 120)]


def test_words_between_and_text():
    assert [w["word"] for w in words_between(TRANSCRIPT, 10.0, 11.0)] == ["I", "bought", "a"]
    assert timestamped_text(TRANSCRIPT).splitlines() == ["[00:10.0] I bought a Lambo", "[01:10.5] later"]


def test_ass_time():
    assert ass_time(0) == "0:00:00.00"
    assert ass_time(3725.456) == "1:02:05.46"


def test_build_ass_highlights_each_word():
    words = words_between(TRANSCRIPT, 10.0, 12.0)
    ass = build_ass(words, 10.0, 30.0, "He {bought} a Lambo")
    dialogue = [line for line in ass.splitlines() if line.startswith("Dialogue")]
    assert dialogue[0].endswith("HE (BOUGHT) A LAMBO")  # braces escaped, upper-cased
    captions = dialogue[1:]
    assert len(captions) == 4  # one event per word
    assert captions[0].startswith("Dialogue: 0,0:00:00.00,0:00:00.30,Caption")
    assert "\\c&H0000E5FF&}BOUGHT" in captions[1]
    assert captions[3].endswith("LAMBO{\\r}")  # second group has a single word


def test_slug():
    assert slug("He bought a LAMBO!!") == "he-bought-a-lambo"
    assert slug("???") == "clip"
