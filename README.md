# Demo 

Learning how to use the Git and Github. https://www.youtube.com/watch?v=RGOj5yH7evk <- Reference
! Editing

## TOGI Clipper

Turns long TOGI videos from the shared Dropbox into ready-to-post vertical clips:

```
Dropbox -> download new videos -> Whisper transcript -> Claude picks the best moments
        -> ffmpeg cuts 9:16 clips with word-by-word captions + hook title
        -> you review, tweak, post
```

Every clip gets a matching `.txt` file with the hook title, why it was picked, a virality score and 2-3 caption options.

### Setup (once)

1. Install Python 3.10+ and (optionally) [ffmpeg](https://ffmpeg.org/download.html). If ffmpeg is not installed, a bundled copy is used.
2. Install dependencies:
   ```bash
   python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. Set keys:
   ```bash
   export ANTHROPIC_API_KEY=sk-ant-...          # https://platform.claude.com
   export DROPBOX_TOKEN=sl....                  # see below
   ```
   **Dropbox token:** create an app at <https://www.dropbox.com/developers/apps> (Scoped access, Full Dropbox), enable the `files.metadata.read` and `sharing.read` permissions, then click *Generate access token*.

### Usage

```bash
python -m togi_clipper run --limit 2      # download up to 2 new videos and clip them
python -m togi_clipper sync               # only download new videos
python -m togi_clipper process            # clip everything in work/raw
python -m togi_clipper process my.mp4 --no-render   # only pick highlights, no rendering
```

Output goes to `work/clips/<video name>/`:

```
01_togi-buys-a-new-lambo.mp4   <- 1080x1920, captions burned in
01_togi-buys-a-new-lambo.txt   <- hook, why, score, caption options
01_togi-buys-a-new-lambo.ass   <- caption file (edit + re-render if a word is wrong)
```

Every step is cached: re-running skips videos that are already transcribed, analysed or rendered. Delete a file to redo that step (e.g. delete a clip's `.mp4` after editing its `.ass`).

### Settings (environment variables)

| Variable | Default | What it does |
|---|---|---|
| `CLIPS_PER_VIDEO` | `8` | Max clips picked per video |
| `WHISPER_MODEL` | `small` | `tiny`/`base` = faster, `medium`/`large-v3` = more accurate |
| `CLAUDE_MODEL` | `claude-opus-5-5` | Model used to pick highlights |
| `TOGI_WORK_DIR` | `work` | Where videos, transcripts and clips are stored |
| `TOGI_DROPBOX_URL` | TOGI folder | Shared Dropbox folder link |

### Before posting

Review every clip. Trim, reorder, change the hook or add your own touch. TOGI pays less for low-effort or copied content, and platforms push down unoriginal reposts. The tool does the boring part; the final creative pass is what gets views.

### Tests

```bash
pytest
```
