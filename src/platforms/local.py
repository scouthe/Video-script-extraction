from __future__ import annotations

from pathlib import Path

from .base import BasePlatform
from ..pipeline.models import VideoItem


class LocalPlatform(BasePlatform):
    name = "local"

    def matches(self, value: str, platform_hint: str | None = None) -> bool:
        path = Path(value)
        return path.exists() and path.is_file()

    def parse(self, value: str) -> VideoItem:
        path = Path(value)
        return VideoItem(
            input_value=value,
            title=path.stem,
            source_url=None,
            video_id=None,
            local_video_path=path,
            local_audio_path=None,
            publish_timestamp=None,
            duration_ms=None,
            platform="local",
        )
