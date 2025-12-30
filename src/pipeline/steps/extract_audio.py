from pathlib import Path

from ..models import VideoItem
from ...utils.ffmpeg import extract_audio as _extract


def extract_audio(item: VideoItem, tmp_dir: Path) -> VideoItem:
    if not item.local_video_path:
        raise ValueError("Missing local_video_path for audio extraction")
    if item.local_audio_path:
        return item

    audio_path = tmp_dir / f"{item.local_video_path.stem}.wav"
    _extract(item.local_video_path, audio_path)
    item.local_audio_path = audio_path
    return item
