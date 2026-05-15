"""
Full integration test (opt-in):
- Set environment variable INTEGRATION_TEST=1 to enable
- Optionally set TEST_PLAYLIST_URL to a full playlist URL; otherwise the built-in playlist id will be used

This script will attempt to download real audio/video for a small playlist (3 items).
It will run three modes: audio, video, and both. It is intentionally opt-in to avoid accidental large downloads.
"""
import os
import sys
import shutil
import time
from pathlib import Path
from src.old.downloader import PlaylistDownloader
from tests.dummy_config import DummyConfig
# Make imports robust when running the script directly from different working directories.
# Ensure the repository root is on sys.path so the script can import `src`.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

if not os.getenv("INTEGRATION_TEST"):
    print("Skipping full integration test (set INTEGRATION_TEST=1 to enable)")
    sys.exit(0)

# Prefer local ./bin/ executables for integration runs when available.
# Set environment variables before importing TempConfig so its class attributes
# pick up these overridden paths.
bin_dir = REPO_ROOT / "bin" / "linux"
if bin_dir.exists():
    ytdlp_path = bin_dir / "yt-dlp"
    if ytdlp_path.exists():
        os.environ.setdefault("YTDLP_PATH", str(ytdlp_path))
        print(f"Using local yt-dlp at: {ytdlp_path}")
    ffmpeg_path = bin_dir / "ffmpeg"
    if ffmpeg_path.exists():
        os.environ.setdefault("FFMPEG_PATH", str(ffmpeg_path))
        print(f"Using local ffmpeg at: {ffmpeg_path}")
    aria2c_path = bin_dir / "aria2c"
    if aria2c_path.exists():
        os.environ.setdefault("ARIA2C_PATH", str(aria2c_path))
        print(f"Using local aria2c at: {aria2c_path}")

# allow caller to override playlist url via env
playlist_url = os.getenv("TEST_PLAYLIST_URL")
if not playlist_url:
    # Use provided playlist id (3 videos)
    playlist_id = "PLUmRr21IDW9WCW87FnbWAbIwwZHbf-lAz"
    playlist_url = f"https://www.youtube.com/playlist?list={playlist_id}"

print(f"Using playlist URL: {playlist_url}")

cfg_base = DummyConfig()

# ensure yt-dlp exists
if not shutil.which(str(cfg_base.yt_dlp_path)):
    print(f"yt-dlp binary not found at '{cfg_base.yt_dlp_path}'. Please install yt-dlp or set YTDLP_PATH environment variable.")
    sys.exit(2)

MODES = ["audio", "video", "both"]

root_tmp = Path("./tests/tmp_integration_full")
root_tmp.mkdir(parents=True, exist_ok=True)

failed = False
for mode in MODES:
    print(f"\n=== Running mode: {mode} ===")
    cfg = DummyConfig()
    # Allow enabling verbose subprocess output from CI by setting YTPL_DEBUG=1
    cfg.debug = bool(os.getenv("YTPL_DEBUG", "0") == "1")
    cfg.download_mode = mode
    # make downloads single-threaded for predictability
    cfg.max_parallel_downloads = 1
    cfg.aria2c_connections = 1

    save_path = root_tmp / mode
    # ensure a clean directory per run
    if save_path.exists():
        try:
            shutil.rmtree(save_path)
        except Exception:
            pass

    playlist = {"url": playlist_url, "save_path": str(save_path), "archive": f"archive_{mode}.txt"}

    downloader = PlaylistDownloader(cfg, playlist, 0)
    # Print resolved binary paths for debugging
    try:
        print(f"Resolved yt-dlp path: {cfg.yt_dlp_path}")
        print(f"Resolved ffmpeg path: {cfg.ffmpeg_path}")
        print(f"Resolved aria2c path: {cfg.aria2c_path}")
    except Exception:
        pass

    try:
        start = time.time()
        downloader.update()
        dur = time.time() - start
        print(f"Mode {mode} completed in {dur:.1f}s")

        # basic verifications
        if mode in ("audio", "both"):
            audio_folder = save_path / "audio"
            mp3s = list(audio_folder.glob("*.mp3")) if audio_folder.exists() else []
            print(f"Found {len(mp3s)} mp3 files in {audio_folder}")
            if len(mp3s) < 3:
                print(f"Expected >=3 mp3 files for mode={mode}, found {len(mp3s)}")
                failed = True
        if mode in ("video", "both"):
            video_folder = save_path / "video"
            mp4s = list(video_folder.glob("*.mp4")) if video_folder.exists() else []
            print(f"Found {len(mp4s)} mp4 files in {video_folder}")
            if len(mp4s) < 3:
                print(f"Expected >=3 mp4 files for mode={mode}, found {len(mp4s)}")
                failed = True

        # check archive has entries
        archive_file = (save_path / f"archive_{mode}.txt")
        if archive_file.exists():
            lines = [line for line in archive_file.read_text(encoding='utf-8').splitlines() if line.strip()]
            print(f"Archive {archive_file} contains {len(lines)} lines")
            if len(lines) < 3:
                print(f"Expected archive to contain >=3 lines, found {len(lines)}")
                # Not necessarily fatal; mark failure but continue
                failed = True
        else:
            print(f"Archive file {archive_file} not found")
            failed = True

    except Exception as ex:
        print(f"Exception during mode {mode}: {ex}")
        failed = True

    # cleanup to avoid leaving large files around
    try:
        if save_path.exists():
            shutil.rmtree(save_path)
            print(f"Cleaned up {save_path}")
    except Exception as ex:
        print(f"Failed to clean up {save_path}: {ex}")

# final cleanup
try:
    if root_tmp.exists():
        shutil.rmtree(root_tmp)
except Exception:
    pass

if failed:
    print("Integration full workflow test encountered failures.")
    sys.exit(3)

print("Integration full workflow test completed successfully")
sys.exit(0)
