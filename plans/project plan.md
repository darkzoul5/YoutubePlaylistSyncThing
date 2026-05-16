# Project Plan

## Subject Area

- Tool for downloading and synchronizing local YouTube playlists.
- Focuses on batch downloading, format selection (audio and/or video), configurable quality and keeping local copies synced with playlist changes.
- Targets power users and archivists who need large-scale, repeatable playlist archiving and ongoing synchronization, with GUI interface.

## Problem

- Users and power-users who manage large or frequently changing YouTube playlists lack a dependable, configurable tool that:
  - correctly detects and downloads new videos while avoiding duplicates,
  - and can be configured easily via file or GUI for repeatable workflows.

## Users Definition

Individuals who need to have a local youtube playlist synced with a large number of videos or audio files

## Functionality Definition

- Multi-format Download:
  - Video only (mp4)
  - Audio only (mp3)
  - Both video and audio (mp3 & mp4)
- Smart Synchronization:
  - Archive tracking (prevents re-downloading existing media)
  - Playlist Pruning (automatically deletes local files no longer in the YouTube playlist)
  - Sequential Renumbering (keeps local files sorted by playlist position)
- Advanced Configuration:
  - Per-playlist settings (Quality, paths, archive file)
  - Global performance options (Parallel downloads, aria2c threading)
  - Path management for yt-dlp, ffmpeg, and aria2c (Docker-aware)
- GUI Integration:
  - Real-time status updates via backend API
  - Visual configuration editor
  - Modern, responsive Qt-based interface

## Platforms

- Desktop: Windows (Primary), Linux

## Architecture & Languages

- Core Engine: Python (yt-dlp)
- Desktop Frontend: PySide6 (Qt for Python)
- Distribution: PyInstaller / Briefcase (Windows .exe, Linux AppImage)
  