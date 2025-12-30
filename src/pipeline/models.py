from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class VideoItem:
    input_value: str
    title: str
    source_url: Optional[str]
    video_id: Optional[str]
    local_video_path: Optional[Path]
    local_audio_path: Optional[Path]
    publish_timestamp: Optional[int] = None
    duration_ms: Optional[int] = None
    platform: str = "auto"
    download_headers: Optional[dict] = None


@dataclass
class Transcript:
    text: str
    raw: dict


@dataclass
class TaskResult:
    item: VideoItem
    transcript: Transcript
    summary: Optional[str]
