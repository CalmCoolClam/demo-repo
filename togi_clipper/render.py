"""Cut a clip, reframe to 9:16 over a blurred background, burn in captions + hook title."""

import json
import re
import shutil
import subprocess
from pathlib import Path

from .config import Config
from .transcribe import words_between

W, H = 1080, 1920
WORDS_PER_CAPTION = 3
HIGHLIGHT = "&H0000E5FF&"  # yellow, ASS is &HAABBGGRR


def ffmpeg_bin() -> str:
    found = shutil.which("ffmpeg")
    if found:
        return found
    import imageio_ffmpeg  # bundled static ffmpeg as fallback

    return imageio_ffmpeg.get_ffmpeg_exe()


def ass_time(t: float) -> str:
    t = max(0.0, t)
    cs = int(round(t * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def ass_escape(text: str) -> str:
    return text.replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", " ")


def build_ass(words: list[dict], clip_start: float, clip_end: float, hook_title: str) -> str:
    """Word-by-word captions (current word highlighted) + a hook title for the first seconds."""
    length = clip_end - clip_start
    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {W}",
        f"PlayResY: {H}",
        "WrapStyle: 0",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
        "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: Caption,Arial,84,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,6,2,2,60,60,560,1",
        "Style: Hook,Arial,72,&H00000000,&H00000000,&H00FFFFFF,&H00FFFFFF,-1,0,0,0,100,100,0,0,3,18,0,8,80,80,260,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    if hook_title:
        lines.append(
            f"Dialogue: 1,{ass_time(0)},{ass_time(min(length, 4.0))},Hook,,0,0,0,,{ass_escape(hook_title).upper()}"
        )

    # Shift to clip-relative time and group into short chunks.
    rel = [
        {**w, "start": w["start"] - clip_start, "end": w["end"] - clip_start}
        for w in words
        if w["word"].strip()
    ]
    for i in range(0, len(rel), WORDS_PER_CAPTION):
        group = rel[i : i + WORDS_PER_CAPTION]
        next_start = rel[i + WORDS_PER_CAPTION]["start"] if i + WORDS_PER_CAPTION < len(rel) else length
        for j, w in enumerate(group):
            start = w["start"]
            end = group[j + 1]["start"] if j + 1 < len(group) else max(w["end"], min(next_start, w["end"] + 0.4))
            text = " ".join(
                f"{{\\c{HIGHLIGHT}}}{ass_escape(g['word']).upper()}{{\\r}}" if k == j else ass_escape(g["word"]).upper()
                for k, g in enumerate(group)
            )
            if end > start:
                lines.append(f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Caption,,0,0,0,,{text}")
    return "\n".join(lines) + "\n"


def slug(text: str, max_len: int = 40) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:max_len].rstrip("-") or "clip"


def render_clip(cfg: Config, video: Path, transcript: dict, clip: dict, index: int) -> Path:
    out_dir = cfg.clips_dir / video.stem
    out_dir.mkdir(parents=True, exist_ok=True)
    name = f"{index:02d}_{slug(clip['hook_title'])}"
    out = out_dir / f"{name}.mp4"
    if out.exists():
        return out

    start, end = clip["start"], clip["end"]
    ass_file = out_dir / f"{name}.ass"
    ass_file.write_text(build_ass(words_between(transcript, start, end), start, end, clip["hook_title"]))
    # Post captions next to the video, ready to copy.
    (out_dir / f"{name}.txt").write_text(
        f"{clip['hook_title']}\n\nWhy: {clip['why']}\nScore: {clip['virality_score']}/10\n\n"
        + "\n\n".join(clip["captions"])
        + "\n"
    )

    vf = (
        f"[0:v]split=2[bg][fg];"
        f"[bg]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=30:5[bgb];"
        f"[fg]scale={W}:-2[fgs];"
        f"[bgb][fgs]overlay=(W-w)/2:(H-h)/2,ass={ass_file.name}[v]"
    )
    cmd = [
        ffmpeg_bin(), "-y", "-loglevel", "error",
        "-ss", f"{start:.2f}", "-to", f"{end:.2f}", "-i", str(video.resolve()),
        "-filter_complex", vf, "-map", "[v]", "-map", "0:a?",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
        out.name,
    ]
    print(f"Rendering {out.relative_to(cfg.work_dir)}")
    # Run inside out_dir so the ass= path needs no escaping.
    subprocess.run(cmd, check=True, cwd=out_dir)
    return out


def render_all(cfg: Config, video: Path, transcript: dict, highlights_file: Path) -> list[Path]:
    clips = json.loads(highlights_file.read_text())["clips"]
    return [render_clip(cfg, video, transcript, c, i + 1) for i, c in enumerate(clips)]
