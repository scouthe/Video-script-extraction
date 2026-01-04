from __future__ import annotations

import json
import re
from typing import Optional

import requests

from .base import BasePlatform
from ..pipeline.models import VideoItem


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) EdgiOS/121.0.2277.107 "
        "Version/17.0 Mobile/15E148 Safari/604.1"
    )
}


def _extract_first_url(text: str) -> Optional[str]:
    urls = re.findall(
        r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|"
        r"(?:%[0-9a-fA-F][0-9a-fA-F]))+",
        text,
    )
    return urls[0] if urls else None


class DouyinPlatform(BasePlatform):
    name = "douyin"

    def matches(self, value: str, platform_hint: str | None = None) -> bool:
        if platform_hint and platform_hint.lower() == "douyin":
            return True
        return "douyin.com" in value or "v.douyin.com" in value

    def parse(self, value: str) -> VideoItem:
        share_url = _extract_first_url(value)
        if not share_url:
            raise ValueError("No valid share link found in input")

        share_response = requests.get(share_url, headers=HEADERS, timeout=20)
        share_response.raise_for_status()
        video_id = share_response.url.split("?")[0].strip("/").split("/")[-1]
        share_url = f"https://www.iesdouyin.com/share/video/{video_id}"

        response = requests.get(share_url, headers=HEADERS, timeout=20)
        response.raise_for_status()

        pattern = re.compile(r"window\._ROUTER_DATA\s*=\s*(.*?)</script>", re.DOTALL)
        find_res = pattern.search(response.text)
        if not find_res or not find_res.group(1):
            raise ValueError("Failed to parse video info from HTML")

        json_data = json.loads(find_res.group(1).strip())
        video_key = "video_(id)/page"
        note_key = "note_(id)/page"

        if video_key in json_data["loaderData"]:
            original_video_info = json_data["loaderData"][video_key]["videoInfoRes"]
        elif note_key in json_data["loaderData"]:
            original_video_info = json_data["loaderData"][note_key]["videoInfoRes"]
        else:
            raise ValueError("Video info not found in JSON")

        data = original_video_info["item_list"][0]
        video_url = data["video"]["play_addr"]["url_list"][0].replace("playwm", "play")
        desc = data.get("desc", "").strip() or f"douyin_{video_id}"
        desc = re.sub(r'[\\/:*?"<>|]', "_", desc)

        create_time = data.get("create_time")
        duration_ms = None
        video_data = data.get("video", {})
        if isinstance(video_data, dict):
            duration_ms = video_data.get("duration")
        if duration_ms is None:
            duration_ms = data.get("duration")

        return VideoItem(
            input_value=value,
            title=desc,
            source_url=video_url,
            video_id=video_id,
            local_video_path=None,
            local_audio_path=None,
            publish_timestamp=create_time,
            duration_ms=duration_ms,
            platform="douyin",
            download_headers=HEADERS,
        )
