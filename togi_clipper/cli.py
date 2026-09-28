"""Command line entry point: python -m togi_clipper <command>."""

import argparse
from pathlib import Path

from . import dropbox_sync, highlights, render, transcribe
from .config import Config
from .dropbox_sync import VIDEO_EXTS


def process_video(cfg: Config, video: Path, skip_render: bool = False) -> None:
    t_file = transcribe.transcribe(cfg, video)
    t = transcribe.load(t_file)
    h_file = highlights.find_highlights(cfg, t_file, t)
    if not skip_render:
        clips = render.render_all(cfg, video, t, h_file)
        print(f"{video.name}: {len(clips)} clips in {cfg.clips_dir / video.stem}")


def local_videos(cfg: Config) -> list[Path]:
    return sorted(p for p in cfg.raw_dir.glob("*") if p.suffix.lower() in VIDEO_EXTS)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="togi_clipper", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_sync = sub.add_parser("sync", help="Download new videos from the TOGI Dropbox")
    p_sync.add_argument("--limit", type=int, help="Download at most N new videos")

    p_proc = sub.add_parser("process", help="Transcribe, find highlights and render clips")
    p_proc.add_argument("videos", nargs="*", type=Path, help="Videos (default: everything in work/raw)")
    p_proc.add_argument("--no-render", action="store_true", help="Stop after picking highlights")

    p_run = sub.add_parser("run", help="sync + process in one go")
    p_run.add_argument("--limit", type=int, help="Download at most N new videos")

    args = parser.parse_args(argv)
    cfg = Config()
    cfg.ensure_dirs()

    if args.cmd == "sync":
        new = dropbox_sync.sync(cfg, args.limit)
        print(f"{len(new)} new video(s) downloaded")
    elif args.cmd == "process":
        for video in args.videos or local_videos(cfg):
            process_video(cfg, video, skip_render=args.no_render)
    elif args.cmd == "run":
        dropbox_sync.sync(cfg, args.limit)
        for video in local_videos(cfg):
            process_video(cfg, video)
