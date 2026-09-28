"""Download new videos from the shared TOGI Dropbox folder.

Needs a Dropbox access token (DROPBOX_TOKEN) from an app you create at
https://www.dropbox.com/developers/apps with the `sharing.read` and
`files.metadata.read` scopes. Files already in work/raw are skipped.
"""

from pathlib import Path

import dropbox
from dropbox.files import FileMetadata, FolderMetadata

from .config import Config

VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}


def _walk(dbx: dropbox.Dropbox, link: dropbox.files.SharedLink, path: str = ""):
    result = dbx.files_list_folder(path=path, shared_link=link)
    while True:
        for entry in result.entries:
            sub = f"{path}/{entry.name}"
            if isinstance(entry, FolderMetadata):
                yield from _walk(dbx, link, sub)
            elif isinstance(entry, FileMetadata):
                yield sub, entry
        if not result.has_more:
            break
        result = dbx.files_list_folder_continue(result.cursor)


def local_name(rel_path: str) -> str:
    """Dropbox path -> file name in work/raw (sub-folders flattened so names stay unique)."""
    return rel_path.strip("/").replace("/", "__")


def sync(cfg: Config, limit: int | None = None, folder: str = "") -> list[Path]:
    """Download videos in `folder` (e.g. "/YouTube Videos") that are not yet on disk.

    Returns every video of that folder that is on disk afterwards (new and old).
    `limit` caps how many new videos are downloaded in this run.
    """
    if not cfg.dropbox_token:
        raise SystemExit("DROPBOX_TOKEN is not set (see README).")
    cfg.ensure_dirs()
    dbx = dropbox.Dropbox(cfg.dropbox_token)
    link = dropbox.files.SharedLink(url=cfg.dropbox_url)

    present: list[Path] = []
    downloaded = 0
    for rel_path, meta in _walk(dbx, link, folder.rstrip("/")):
        if Path(meta.name).suffix.lower() not in VIDEO_EXTS:
            continue
        dest = cfg.raw_dir / local_name(rel_path)
        if dest.exists() and dest.stat().st_size == meta.size:
            present.append(dest)
            continue
        if limit is not None and downloaded >= limit:
            continue
        print(f"Downloading {rel_path} ({meta.size / 1e6:.0f} MB)")
        tmp = dest.with_suffix(dest.suffix + ".part")
        _, resp = dbx.sharing_get_shared_link_file(url=cfg.dropbox_url, path=rel_path)
        with open(tmp, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1 << 20):
                f.write(chunk)
        tmp.rename(dest)
        present.append(dest)
        downloaded += 1
    print(f"{downloaded} new video(s) downloaded, {len(present)} in {folder or 'Dropbox'}")
    return present
