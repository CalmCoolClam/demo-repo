"""Transcribe a video locally with faster-whisper, keeping word-level timestamps."""

import json
from pathlib import Path

from .config import Config


def transcript_path(cfg: Config, video: Path) -> Path:
    return cfg.transcripts_dir / f"{video.stem}.json"


def transcribe(cfg: Config, video: Path) -> Path:
    out = transcript_path(cfg, video)
    if out.exists():
        return out
    from faster_whisper import WhisperModel  # heavy import, only when needed

    print(f"Transcribing {video.name} with whisper-{cfg.whisper_model}")
    model = WhisperModel(cfg.whisper_model, device="auto", compute_type="auto")
    segments, info = model.transcribe(str(video), word_timestamps=True, vad_filter=True)

    data = {"video": video.name, "language": info.language, "duration": info.duration, "segments": []}
    for seg in segments:
        data["segments"].append({
            "start": round(seg.start, 2),
            "end": round(seg.end, 2),
            "text": seg.text.strip(),
            "words": [
                {"start": round(w.start, 2), "end": round(w.end, 2), "word": w.word.strip()}
                for w in (seg.words or [])
            ],
        })
    cfg.ensure_dirs()
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1))
    return out


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def words_between(transcript: dict, start: float, end: float) -> list[dict]:
    """All words whose midpoint falls inside [start, end]."""
    return [
        w
        for seg in transcript["segments"]
        for w in seg["words"]
        if start <= (w["start"] + w["end"]) / 2 <= end
    ]


def timestamped_text(transcript: dict) -> str:
    """Compact `[mm:ss.s] text` lines for the highlight picker."""
    lines = []
    for seg in transcript["segments"]:
        m, s = divmod(seg["start"], 60)
        lines.append(f"[{int(m):02d}:{s:04.1f}] {seg['text']}")
    return "\n".join(lines)
