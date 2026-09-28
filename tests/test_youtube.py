import pytest

from togi_clipper.highlights import format_moments
from togi_clipper.youtube import (
    best_match,
    channel_handle,
    match_file,
    hot_moments,
    normalize_title,
    parse_duration,
    timestamps_in,
    video_id,
)

DURATION = 3 * 3600.0


def test_timestamps_in():
    assert timestamps_in("12:34 LMAO", DURATION) == [754.0]
    assert timestamps_in("1:02:05 and 0:45 lol", DURATION) == [3725.0, 45.0]
    assert timestamps_in("bro was up at 3:15am", DURATION) == [195.0]
    assert timestamps_in("score 12:345, 2025:10:10, 12:3", DURATION) == []  # not timestamps
    assert timestamps_in("5:00:00", DURATION) == []  # beyond the video


def test_video_id():
    assert video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=10s") == "dQw4w9WgXcQ"
    assert video_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert video_id("dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    with pytest.raises(ValueError):
        video_id("https://example.com")


def test_parse_duration():
    assert parse_duration("PT1H2M3S") == 3723
    assert parse_duration("PT45S") == 45
    assert parse_duration("P1DT1S") == 86401


def test_hot_moments_clusters_and_ranks():
    comments = [
        {"text": "10:00 😭😭", "likes": 500},
        {"text": "10:08 the lambo part", "likes": 50},
        {"text": "10:12 no way", "likes": 0},
        {"text": "45:00 funny", "likes": 3},
        {"text": "great stream", "likes": 1000},  # no timestamp, ignored
        # a "best of" list: each stamp counts a quarter
        {"text": "1:00 2:00 3:00 45:05", "likes": 20},
    ]
    moments = hot_moments(comments, DURATION)
    top = moments[0]
    assert top["mentions"] == 3 and top["first"] == 600 and top["last"] == 612
    assert 600 <= top["time"] < 605  # pulled toward the most-liked comment
    assert top["comments"][0] == "10:00 😭😭"
    assert moments[1]["first"] == 2700 and moments[1]["mentions"] == 2
    assert {m["first"] for m in moments} == {600, 2700, 60, 120, 180}


def test_format_moments_quotes_comments():
    text = format_moments([{"time": 605.5, "score": 3.2, "mentions": 2, "comments": ['he said "no"']}])
    assert text == '[10:05.5] score 3.2, 2 mentions. Comments: "he said \\"no\\""'


def result(vid, title):
    return {"id": {"videoId": vid}, "snippet": {"title": title}}


def test_normalize_title():
    assert normalize_title("YouTube Videos__TOGI Buys A LAMBO!!.mp4") == "togi buys a lambo"
    assert normalize_title("I&#39;m done | TOGI") == "i m done togi"


def test_best_match_picks_closest_title():
    results = [
        result("aaaaaaaaaaa", "TOGI reacts to Lambo prices"),
        result("bbbbbbbbbbb", "I Bought My Dream Lambo (TOGI)"),
        result("ccccccccccc", "Cooking stream"),
    ]
    m = best_match("YouTube Videos__I bought my dream lambo.mp4", results)
    assert m["id"] == "bbbbbbbbbbb" and m["similarity"] > 0.8
    assert best_match("Completely different video.mp4", results) is None


def test_channel_handle():
    assert channel_handle("https://youtube.com/@shanestoffer?si=g-qq5WDelP1tL4fL") == "shanestoffer"
    assert channel_handle("@togiextras") == "togiextras"
    assert channel_handle("https://www.youtube.com/channel/UCabc_123") == "UCabc_123"


class FakeSearch:
    def __init__(self, by_channel):
        self.by_channel, self.calls = by_channel, []

    def search(self):
        return self

    def videos(self):
        return self

    def list(self, **kw):
        self.calls.append(kw)
        if "q" in kw:
            data = {"items": self.by_channel[kw["channelId"]]}
        else:
            data = {"items": [{"snippet": {"title": "t"}, "contentDetails": {"duration": "PT1H"}}]}
        return type("Req", (), {"execute": lambda self_: data})()


def test_match_file_tries_channels_in_order(tmp_path, monkeypatch):
    from togi_clipper import youtube
    from togi_clipper.config import Config

    fake = FakeSearch({
        "UCmain": [result("aaaaaaaaaaa", "Lambo prices are crazy")],
        "UCextras": [result("bbbbbbbbbbb", "I Bought My Dream Lambo")],
    })
    monkeypatch.setattr(youtube, "_client", lambda cfg: fake)
    cfg = Config(work_dir=tmp_path)
    video = tmp_path / "YouTube Videos__I bought my dream lambo.mp4"

    m = match_file(cfg, video, ["UCmain", "UCextras"])
    assert m["id"] == "bbbbbbbbbbb" and m["duration"] == 3600
    assert [c.get("channelId") for c in fake.calls if "q" in c] == ["UCmain", "UCextras"]

    # A good match on the first channel stops the search there.
    fake.calls.clear()
    fake.by_channel["UCmain"] = [result("ccccccccccc", "I bought my dream Lambo!")]
    match_file(cfg, tmp_path / "other__I bought my dream lambo.mp4", ["UCmain", "UCextras"])
    assert [c.get("channelId") for c in fake.calls if "q" in c] == ["UCmain"]

    # Cached: no new searches.
    fake.calls.clear()
    assert match_file(cfg, video, ["UCmain", "UCextras"])["id"] == "bbbbbbbbbbb"
    assert fake.calls == []
