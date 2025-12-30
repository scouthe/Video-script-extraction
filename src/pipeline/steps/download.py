from pathlib import Path
import requests
from tqdm import tqdm

from ..models import VideoItem


def download_video(item: VideoItem, tmp_dir: Path) -> VideoItem:
    if item.local_video_path:
        return item
    if not item.source_url:
        raise ValueError("Missing source_url for download")

    filename = f"{item.video_id or 'video'}.mp4"
    video_path = tmp_dir / filename

    headers = item.download_headers or {}
    response = requests.get(item.source_url, headers=headers, stream=True, timeout=30)
    response.raise_for_status()

    total = int(response.headers.get("content-length", 0))
    with open(video_path, "wb") as f, tqdm(
        total=total, unit="B", unit_scale=True, desc=f"Downloading {filename}"
    ) as progress:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
                progress.update(len(chunk))

    item.local_video_path = video_path
    return item
