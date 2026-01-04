from __future__ import annotations

from abc import ABC, abstractmethod

from ..pipeline.models import VideoItem


class BasePlatform(ABC):
    name: str = "base"

    @abstractmethod
    def matches(self, value: str, platform_hint: str | None = None) -> bool:
        raise NotImplementedError

    @abstractmethod
    def parse(self, value: str) -> VideoItem:
        raise NotImplementedError
