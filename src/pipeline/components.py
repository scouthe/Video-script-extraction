from __future__ import annotations

from pathlib import Path
import requests

from ..pipeline.models import VideoItem
from ..utils.ffmpeg import extract_audio as _extract_audio
from ..utils.text import clean_text, split_paragraphs
from openai import OpenAI


class VideoDownloader:
    def download(self, item: VideoItem, tmp_dir: Path) -> VideoItem:
        if item.local_video_path:
            return item
        if not item.source_url:
            raise ValueError("Missing source_url for download")

        filename = f"{item.video_id or 'video'}.mp4"
        video_path = tmp_dir / filename
        headers = item.download_headers or {}
        response = requests.get(item.source_url, headers=headers, stream=True, timeout=30)
        response.raise_for_status()

        with open(video_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        item.local_video_path = video_path
        return item


class AudioExtractor:
    def extract(self, item: VideoItem, tmp_dir: Path) -> VideoItem:
        if not item.local_video_path:
            raise ValueError("Missing local_video_path for audio extraction")
        if item.local_audio_path:
            return item
        audio_path = tmp_dir / f"{item.local_video_path.stem}.wav"
        _extract_audio(item.local_video_path, audio_path)
        item.local_audio_path = audio_path
        return item


class TextPostProcessor:
    def process(self, text: str) -> list[str]:
        cleaned = clean_text(text)
        paragraphs = split_paragraphs(cleaned)
        return paragraphs if paragraphs else [cleaned]


class Summarizer:
    def summarize(self, text: str, api_key: str, base_url: str, model: str) -> str:
        client = OpenAI(api_key=api_key, base_url=base_url)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a concise Chinese assistant."},
                {"role": "user", "content": f"请用一句话总结下面文案：\n{text}"},
            ],
            temperature=0.2,
        )
        return response.choices[0].message.content.strip()
