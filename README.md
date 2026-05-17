# YouTube Playlist Sync

[![Build Release](https://github.com/darkzoul5/YoutubePlaylistDownloader/actions/workflows/build-release.yml/badge.svg)](https://github.com/darkzoul5/YoutubePlaylistDownloader/actions/workflows/build-release.yml)
[![Unit tests](https://github.com/darkzoul5/YoutubePlaylistDownloader/actions/workflows/unit-tests.yml/badge.svg?branch=main)](https://github.com/darkzoul5/YoutubePlaylistDownloader/actions/workflows/unit-tests.yml)

A cross-platform tool for downloading and keeping in sync a local copy of entire YouTube playlists as MP3 or MP4 files, using [yt-dlp](https://github.com/yt-dlp/yt-dlp) & [ffmpeg](https://ffmpeg.org/).

Supports audio, video, or both download modes, music and videos are numbered as they are on your youtube playlist, playlist cleanup, and configurable parallel download options.
Local-first YouTube playlist synchronization client.

## What's Included

- GUI (PySide6) playlist manager + sync runner
- Scanner (yt-dlp extract-only), diff engine, filesystem scan
- Safe reordering via two-pass rename, recycle deletions
- Async download queue with simple retry (yt-dlp Python API)
- SQLite metadata (`last_sync`, download state)

## Requirements

- If you download a `-ffmpeg` release: no extra dependencies
- If you download a non-ffmpeg release: install `ffmpeg` and ensure it's on PATH (needed for `audio` and `both` modes)

## Download

Download the latest release from this repo's Releases page and pick one:

- `ytpl-sync-windows-{version}-ffmpeg.zip` / `ytpl-sync-linux-{version}-ffmpeg.tar.gz` (ffmpeg bundled)
- `ytpl-sync-windows-{version}.zip` / `ytpl-sync-linux-{version}.tar.gz` (no ffmpeg bundled)

## Configure
Application uses a json config that canbe edited from UI or manually

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
      "save_path": "./downloads",
      "name": "my favorite playlist"
    }
  ]
}
```

`max_download_quality`:

- Limits yt-dlp download quality (e.g. `"2160p"`, `"1440p"`, `"1080p"`, `"720p"`, `"360p"`). This only affects the downloaded video format selection.
- Use `"best"` for no height cap (highest available).
- If the requested max quality isn't available for a video, the best available quality is chosen.

`download_mode`:

- `video`: download playlist videos as `.mp4` (no ffmpeg required)
- `audio`: download video, extract `.mp3`, delete the video file
- `both`: download video, extract `.mp3`, keep both files

Queue / retry:

- `max_parallel_downloads`: number of concurrent download workers.
- `retry_max_retries`: how many times a failed download job is retried.
- `retry_delay_seconds`: base delay before retry; increases with backoff.

## Run

- Run `ytpl-sync.exe` (GUI).

## Tray
 
- The app supports minimizing to tray on close if the OS provides a system tray; use the tray icon menu to quit.
- Tray behavior settings (Settings page):
  - `close_to_tray`: close hides to tray (keeps running).
  - `minimize_to_tray`: minimize hides to tray.
  - `start_minimized_to_tray`: start hidden in tray.

## Data & Layout

- Database: `db/app.db`
- Outputs: `<save_path>/audio` and/or `<save_path>/video`
- Recycle bin: `<save_path>/.recycle/{audio,video}`

## Roadmap (short)

- Scheduler (periodic sync), richer retries/logging
- Enhanced config validation
- UX polish (settings, progress, error messages)
