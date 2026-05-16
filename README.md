# YouTube Playlist Sync

[![Build Release](https://github.com/darkzoul5/YoutubePlaylistDownloader/actions/workflows/build_v2.yml/badge.svg)](https://github.com/darkzoul5/YoutubePlaylistDownloader/actions/workflows/build_v2.yml)
[![Unit tests](https://github.com/darkzoul5/YoutubePlaylistDownloader/actions/workflows/unit-tests.yml/badge.svg?branch=main)](https://github.com/darkzoul5/YoutubePlaylistDownloader/actions/workflows/unit-tests.yml)

A cross-platform tool for downloading and keeping in sync a local copy of entire YouTube playlists as MP3 or MP4 files, using [yt-dlp](https://github.com/yt-dlp/yt-dlp) & [ffmpeg](https://ffmpeg.org/).

Supports audio, video, or both download modes, music and videos are numbered as they are on your youtube playlist, playlist cleanup, and configurable parallel download options.
Local-first YouTube playlist synchronization client.

## What’s Included

- Scanner (yt-dlp extract-only), diff engine, filesystem scan
- Safe reordering via two-pass rename, recycle deletions
- Async download queue with simple retry (yt-dlp Python API)
- SQLite metadata; DB updates on rename/download/delete; `last_sync`
- Optional event publishing for future GUI/logs

## Requirements

- Python 3.10+
- `ffmpeg` (needed for `audio` and `both` modes)

Quick start:

Download the latest release from [releases](https://github.com/darkzoul5/YoutubePlaylistSyncThing/releases) page

## Configure

On first run, the app will auto-create a default `config/yt-playlist-config.json` (if missing).

Create/edit `config/yt-playlist-config.json`:

```json
{
  "ffmpeg_path": "./bin/ffmpeg.exe",
  "max_parallel_downloads": 2,
  "retry_max_retries": 2,
  "retry_delay_seconds": 1.5,
  "playlists": [
    {
      "url": "https://www.youtube.com/playlist?list=YOUR_PLAYLIST_ID",
      "download_mode": "video",
      "max_download_quality": "1080p",
      "save_path": "./downloads"
    }
  ]
}
```

Defaults:

- `ffmpeg_path`: `./bin/ffmpeg.exe` (Windows) or `./bin/ffmpeg` (Linux)
- `download_mode`: `video`
- `max_download_quality`: `1080p`
- `save_path`: `./downloads`
- `max_parallel_downloads`: `2`
- `retry_max_retries`: `2`
- `retry_delay_seconds`: `1.5`

`max_download_quality`:

- Limits yt-dlp download quality (e.g. `"1080p"`, `"720p"`, `"360p"`). This only affects the downloaded video format selection.
- If the requested max quality isn't available for a video, the best available quality is chosen.

`download_mode`:

- `video`: download playlist videos as muxed `.mp4` (no ffmpeg processing)
- `audio`: download muxed `.mp4`, extract `.mp3`, delete the `.mp4`
- `both`: download muxed `.mp4`, extract `.mp3`, keep both files

Queue / retry:

- `max_parallel_downloads`: number of concurrent download workers.
- `retry_max_retries`: how many times a failed download job is retried.
- `retry_delay_seconds`: base delay before retry; increases with backoff.

## Run

- Compute-only:

```bash
python -m src.app.cli
```

- Apply actions:

```bash
python -m src.app.cli --apply
```

- Single playlist (0-based index):

```bash
python -m src.app.cli --apply --playlist 0
```

## Data & Layout

- Database: `app/data/app.db`
- Outputs: `<save_path>/audio` and/or `<save_path>/video`
- Recycle bin: `<save_path>/.recycle/{audio,video}`

## Roadmap (short)

- Scheduler (periodic sync), richer retries/logging
- GUI (PySide6) wired to EventBus
- Enhanced config validation
