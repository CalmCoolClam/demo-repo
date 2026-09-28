"""Command line entry point: python -m togi_clipper <command>."""

import argparse
import json
from pathlib import Path

from . import dropbox_sync, highlights, render, transcribe, youtube
from .config import Config
from .dropbox_sync import VIDEO_EXTS


def process_video(cfg: Config, video: Path, skip_render: bool = False, moments: list[dict] | None = None) -> None:
    t_file = transcribe.transcribe(cfg, video)
    t = transcribe.load(t_file)
    h_file = highlights.find_highlights(cfg, t_file, t, moments)
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

    p_yt = sub.add_parser("youtube", help="Clip official TOGI YouTube videos around the moments viewers comment on")
    src = p_yt.add_mutually_exclusive_group(required=True)
    src.add_argument("--latest", type=int, metavar="N", help="The channel's N newest long videos")
    src.add_argument("--video", nargs="+", metavar="URL", help="Specific video links or IDs")
    p_yt.add_argument("--moments-only", action="store_true", help="Only print the hot moments, no download/clips")

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
    elif args.cmd == "youtube":
        if args.latest:
            if not cfg.youtube_channel:
                raise SystemExit("TOGI_YT_CHANNEL is not set (the channel's @handle, see README).")
            infos = youtube.latest_uploads(cfg, args.latest)
        else:
            infos = [youtube.video_info(cfg, youtube.video_id(v)) for v in args.video]
        for info in infos:
            data = json.loads(youtube.collect(cfg, info).read_text())
            if args.moments_only:
                print(f"\n{info['title']} (https://youtu.be/{info['id']})")
                for m in data["moments"]:
                    mm, ss = divmod(int(m["time"]), 60)
                    print(f"  {mm:02d}:{ss:02d}  score {m['score']:>5}  {m['comments'][0][:70]!r}")
                continue
            process_video(cfg, youtube.download(cfg, info["id"]), moments=data["moments"])
