from __future__ import annotations

from typing import Iterable

from .base import BasePlatform
from .douyin import DouyinPlatform
from .bilibili import BilibiliPlatform
from .local import LocalPlatform
from ..pipeline.models import VideoItem


class PlatformResolver:
    def __init__(self, platforms: Iterable[BasePlatform] | None = None) -> None:
        self.platforms = list(platforms) if platforms else [
            LocalPlatform(),
            BilibiliPlatform(),
            DouyinPlatform(),
        ]

    def resolve(self, value: str, platform_hint: str | None = None) -> VideoItem:
        for platform in self.platforms:
            if platform.matches(value, platform_hint):
                return platform.parse(value)
        raise ValueError("Unsupported input for platform resolution")
