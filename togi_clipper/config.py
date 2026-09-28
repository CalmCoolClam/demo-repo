"""Settings, read from environment variables (or a .env file you source yourself)."""

import os
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_DROPBOX_URL = (
    "https://www.dropbox.com/scl/fo/szt65agmfc2qeitopoekb/"
    "ALZGY9zVBr0VYzqn_0ul9PY?rlkey=1sei6j4emz5nwi61ax6nbrjhp&dl=0"
)


@dataclass
class Config:
    work_dir: Path = field(default_factory=lambda: Path(os.getenv("TOGI_WORK_DIR", "work")))
    dropbox_url: str = field(default_factory=lambda: os.getenv("TOGI_DROPBOX_URL", DEFAULT_DROPBOX_URL))
    dropbox_token: str | None = field(default_factory=lambda: os.getenv("DROPBOX_TOKEN"))
    youtube_api_key: str | None = field(default_factory=lambda: os.getenv("YOUTUBE_API_KEY"))
    youtube_channel: str = field(default_factory=lambda: os.getenv("TOGI_YT_CHANNEL", ""))
    # Sub-folder of the shared Dropbox with the full YouTube uploads.
    dropbox_youtube_folder: str = field(
        default_factory=lambda: os.getenv("TOGI_DROPBOX_YT_FOLDER", "/YouTube Videos")
    )
    whisper_model: str = field(default_factory=lambda: os.getenv("WHISPER_MODEL", "small"))
    claude_model: str = field(default_factory=lambda: os.getenv("CLAUDE_MODEL", "claude-opus-5-5"))
    clips_per_video: int = field(default_factory=lambda: int(os.getenv("CLIPS_PER_VIDEO", "8")))
    min_clip_seconds: float = 15.0
    max_clip_seconds: float = 75.0

    @property
    def raw_dir(self) -> Path:
        return self.work_dir / "raw"

    @property
    def transcripts_dir(self) -> Path:
        return self.work_dir / "transcripts"

    @property
    def highlights_dir(self) -> Path:
        return self.work_dir / "highlights"

    @property
    def clips_dir(self) -> Path:
        return self.work_dir / "clips"

    def ensure_dirs(self) -> None:
        for d in (self.raw_dir, self.transcripts_dir, self.highlights_dir, self.clips_dir):
            d.mkdir(parents=True, exist_ok=True)
