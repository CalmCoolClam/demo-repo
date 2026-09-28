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


def sync(cfg: Config, limit: int | None = None) -> list[Path]:
    """Download videos not yet on disk. Returns the newly downloaded paths."""
    if not cfg.dropbox_token:
        raise SystemExit("DROPBOX_TOKEN is not set (see README).")
    cfg.ensure_dirs()
    dbx = dropbox.Dropbox(cfg.dropbox_token)
    link = dropbox.files.SharedLink(url=cfg.dropbox_url)

    new: list[Path] = []
    for rel_path, meta in _walk(dbx, link):
        if Path(meta.name).suffix.lower() not in VIDEO_EXTS:
            continue
        # Flatten sub-folders into the file name so names stay unique.
        dest = cfg.raw_dir / rel_path.strip("/").replace("/", "__")
        if dest.exists() and dest.stat().st_size == meta.size:
            continue
        print(f"Downloading {rel_path} ({meta.size / 1e6:.0f} MB)")
        tmp = dest.with_suffix(dest.suffix + ".part")
        _, resp = dbx.sharing_get_shared_link_file(url=cfg.dropbox_url, path=rel_path)
        with open(tmp, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1 << 20):
                f.write(chunk)
        tmp.rename(dest)
        new.append(dest)
        if limit and len(new) >= limit:
            break
    return new
