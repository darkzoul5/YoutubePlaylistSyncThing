import argparse
import logging
import subprocess
from .config import ConfigLoader, is_docker
from .manager import PlaylistManager


def configure_logging(debug: bool):
    level = logging.DEBUG if debug else logging.INFO
    fmt = "%(asctime)s %(levelname)s: %(message)s" if debug else "%(levelname)s: %(message)s"
    logging.basicConfig(level=level, format=fmt)


def update_yt_dlp(yt_dlp_path: str, debug: bool = False):
    logger = logging.getLogger(__name__)
    try:
        if debug:
            subprocess.run([yt_dlp_path, "-U"], check=True)
        else:
            subprocess.run([yt_dlp_path, "-U"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        logger.info("yt-dlp is up to date.")
    except subprocess.CalledProcessError:
        logger.warning("Could not update yt-dlp: Internet unavailable or cannot reach update server")


def main():
    parser = argparse.ArgumentParser(prog="yt-playlist")
    parser.add_argument("-c", "--config", default="yt-playlist-config.json", help="Path to config file")
    parser.add_argument("-d", "--debug", action="store_true", help="Enable debug logging and show binary output")
    parser.add_argument("-p", "--prune", dest="prune", action="store_true", help="Enable pruning: delete files not present in the playlist")
    parser.add_argument("-y", "--yes", "--non-interactive", dest="yes", action="store_true", help="Run non-interactively (auto-confirm prompts, used with --prune)")
    args = parser.parse_args()

    configure_logging(args.debug)
    logger = logging.getLogger(__name__)

    cfg = ConfigLoader(args.config)
    if not is_docker():
        update_yt_dlp(cfg.yt_dlp_path, debug=args.debug)

    manager = PlaylistManager(cfg, debug=args.debug)
    # support non-interactive mode for CI
    setattr(cfg, "non_interactive", bool(args.yes))
    setattr(cfg, "prune", bool(args.prune))
    logger.debug("Starting PlaylistManager with debug=%s", args.debug)
    manager.run()
