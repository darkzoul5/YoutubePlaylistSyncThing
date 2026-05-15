import time
import logging

from .downloader import PlaylistDownloader


class PlaylistManager:
    def __init__(self, config, debug: bool = False):
        self.logger = logging.getLogger(__name__)
        self.config = config
        # store debug on config so PlaylistDownloader __init__ can pick it up
        setattr(self.config, "debug", bool(debug))
        self.playlists = [PlaylistDownloader(config, pl, idx) for idx, pl in enumerate(config.playlists)]

    def run(self):
        total_connections = self.config.max_parallel_downloads * self.config.aria2c_connections
        if total_connections > 100:
            self.logger.warning(
                "Total connections (%d × %d = %d) may overload your network! Pausing 5 seconds...",
                self.config.max_parallel_downloads,
                self.config.aria2c_connections,
                total_connections,
            )
            time.sleep(5)

        for playlist in self.playlists:
            playlist.update()
