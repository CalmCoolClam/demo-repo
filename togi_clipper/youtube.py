"""Find the moments viewers point at in the comments of the official TOGI YouTube videos.

Comments are read with the official YouTube Data API v3 (needs YOUTUBE_API_KEY).
Timestamps like "12:34 LMAO" are collected, weighted by likes and grouped into
"hot moments" that are handed to the highlight picker.
"""

import json
import math
import re
from pathlib import Path

from .config import Config

TIMESTAMP = re.compile(r"(?<![\d:])(?:(\d{1,2}):)?(\d{1,3}):([0-5]\d)(?![\d:])")
VIDEO_ID = re.compile(r"(?:v=|youtu\.be/|shorts/|live/)([A-Za-z0-9_-]{11})")
CLUSTER_GAP = 15.0  # timestamps closer than this belong to the same moment


def _client(cfg: Config):
    from googleapiclient.discovery import build  # heavy import, only when needed

    if not cfg.youtube_api_key:
        raise SystemExit("YOUTUBE_API_KEY is not set (see README).")
    return build("youtube", "v3", developerKey=cfg.youtube_api_key, cache_discovery=False)


def video_id(url_or_id: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", url_or_id):
        return url_or_id
    m = VIDEO_ID.search(url_or_id)
    if not m:
        raise ValueError(f"Not a YouTube video link: {url_or_id}")
    return m.group(1)


def parse_duration(iso: str) -> float:
    """ISO 8601 duration from the API (PT1H2M3S) -> seconds."""
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso)
    if not m:
        return 0.0
    d, h, mi, s = (int(x or 0) for x in m.groups())
    return float(d * 86400 + h * 3600 + mi * 60 + s)


def latest_uploads(cfg: Config, count: int, min_seconds: float = 180) -> list[dict]:
    """Newest long-form uploads of the channel (Shorts are skipped)."""
    yt = _client(cfg)
    handle = cfg.youtube_channel.lstrip("@")
    lookup = {"id": handle} if handle.startswith("UC") else {"forHandle": handle}
    items = yt.channels().list(part="contentDetails", **lookup).execute().get("items", [])
    if not items:
        raise SystemExit(f"YouTube channel not found: {cfg.youtube_channel}")
    uploads = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]

    ids = [
        it["contentDetails"]["videoId"]
        for it in yt.playlistItems().list(part="contentDetails", playlistId=uploads, maxResults=50)
        .execute()["items"]
    ]
    videos = yt.videos().list(part="snippet,contentDetails,statistics", id=",".join(ids)).execute()["items"]
    out = []
    for v in videos:
        duration = parse_duration(v["contentDetails"]["duration"])
        if duration >= min_seconds:
            out.append({"id": v["id"], "title": v["snippet"]["title"], "duration": duration})
    return out[:count]


def video_info(cfg: Config, vid: str) -> dict:
    items = _client(cfg).videos().list(part="snippet,contentDetails", id=vid).execute()["items"]
    if not items:
        raise SystemExit(f"Video not found: {vid}")
    v = items[0]
    return {"id": vid, "title": v["snippet"]["title"], "duration": parse_duration(v["contentDetails"]["duration"])}


def fetch_comments(cfg: Config, vid: str, max_pages: int = 10) -> list[dict]:
    """Top-level comments (most relevant first), up to 100 per page."""
    yt = _client(cfg)
    comments, token = [], None
    for _ in range(max_pages):
        resp = yt.commentThreads().list(
            part="snippet", videoId=vid, order="relevance", maxResults=100,
            textFormat="plainText", pageToken=token,
        ).execute()
        for item in resp.get("items", []):
            s = item["snippet"]["topLevelComment"]["snippet"]
            comments.append({"text": s["textDisplay"], "likes": s.get("likeCount", 0)})
        token = resp.get("nextPageToken")
        if not token:
            break
    return comments


def timestamps_in(text: str, duration: float) -> list[float]:
    out = []
    for h, m, s in TIMESTAMP.findall(text):
        t = int(h or 0) * 3600 + int(m) * 60 + int(s)
        if 0 < t < duration:
            out.append(float(t))
    return out


def hot_moments(comments: list[dict], duration: float, top: int = 15) -> list[dict]:
    """Group timestamp mentions into moments, scored by mentions and likes."""
    mentions = []
    for c in comments:
        ts = timestamps_in(c["text"], duration)
        weight = (1 + math.log1p(c["likes"])) / max(1, len(ts))  # "best-of" lists count less per stamp
        mentions += [(t, weight, c) for t in ts]
    mentions.sort(key=lambda m: m[0])

    clusters: list[list] = []
    for m in mentions:
        if clusters and m[0] - clusters[-1][-1][0] <= CLUSTER_GAP:
            clusters[-1].append(m)
        else:
            clusters.append([m])

    moments = []
    for cl in clusters:
        score = sum(w for _, w, _ in cl)
        best = sorted({id(c): c for _, _, c in cl}.values(), key=lambda c: -c["likes"])[:3]
        moments.append({
            "time": round(sum(t * w for t, w, _ in cl) / score, 1),
            "first": cl[0][0],
            "last": cl[-1][0],
            "mentions": len(cl),
            "score": round(score, 2),
            "comments": [c["text"][:200] for c in best],
        })
    return sorted(moments, key=lambda m: -m["score"])[:top]


def download(cfg: Config, vid: str) -> Path:
    """Download the video with yt-dlp (max 1080p) into work/raw/<id>.mp4."""
    import yt_dlp

    cfg.ensure_dirs()
    out = cfg.raw_dir / f"{vid}.mp4"
    if out.exists():
        return out
    opts = {
        "format": "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080]/b",
        "merge_output_format": "mp4",
        "outtmpl": str(cfg.raw_dir / "%(id)s.%(ext)s"),
        "quiet": True,
        "noprogress": True,
    }
    try:
        from .render import ffmpeg_bin

        opts["ffmpeg_location"] = ffmpeg_bin()
    except Exception:
        pass
    print(f"Downloading https://youtu.be/{vid}")
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([f"https://www.youtube.com/watch?v={vid}"])
    return out


def moments_path(cfg: Config, vid: str) -> Path:
    return cfg.transcripts_dir / f"{vid}.moments.json"


def collect(cfg: Config, info: dict) -> Path:
    """Fetch comments and save the hot moments for one video."""
    out = moments_path(cfg, info["id"])
    if out.exists():
        return out
    print(f"Reading comments on: {info['title']}")
    comments = fetch_comments(cfg, info["id"])
    moments = hot_moments(comments, info["duration"])
    cfg.ensure_dirs()
    out.write_text(json.dumps({**info, "comments_read": len(comments), "moments": moments}, ensure_ascii=False, indent=2))
    print(f"  {len(comments)} comments, {len(moments)} hot moments")
    return out
