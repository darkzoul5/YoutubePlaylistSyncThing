import os


class DummyConfig:
    """Small test configuration object used by unit and integration tests.

    Adjust attributes via environment variables where appropriate.
    """
    yt_dlp_path = os.getenv("YTDLP_PATH", "yt-dlp")
    ffmpeg_path = os.getenv("FFMPEG_PATH", "ffmpeg")
    aria2c_path = os.getenv("ARIA2C_PATH", "aria2c")
    max_parallel_downloads = int(os.getenv("TEST_MAX_PARALLEL", "2"))
    aria2c_connections = int(os.getenv("TEST_ARIA2C_CONN", "2"))
    download_mode = os.getenv("TEST_DOWNLOAD_MODE", "audio")
    max_download_quality = os.getenv("TEST_MAX_DOWNLOAD_QUALITY", "1080p")
    # runtime flags
    debug = False
    non_interactive = False
    prune = False
