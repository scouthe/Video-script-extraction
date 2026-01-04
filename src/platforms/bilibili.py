from __future__ import annotations

import re
import requests

from .base import BasePlatform
from ..pipeline.models import VideoItem


BILIBILI_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.bilibili.com/",
}


def _resolve_bilibili_url(value: str) -> str:
    if value.startswith("http://") or value.startswith("https://"):
        resp = requests.get(value, headers=BILIBILI_HEADERS, timeout=20, allow_redirects=True)
        resp.raise_for_status()
        return resp.url
    return value


class BilibiliPlatform(BasePlatform):
    name = "bilibili"

    def matches(self, value: str, platform_hint: str | None = None) -> bool:
        if platform_hint and platform_hint.lower() == "bilibili":
            return True
        return "bilibili.com" in value or "b23.tv" in value

    def parse(self, value: str) -> VideoItem:
        url = _resolve_bilibili_url(value)
        match = re.search(r"BV[0-9A-Za-z]+", url)
        if not match:
            raise ValueError("Failed to parse Bilibili BV id from input")
        bvid = match.group(0)

        view_api = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
        view_resp = requests.get(view_api, headers=BILIBILI_HEADERS, timeout=20)
        view_resp.raise_for_status()
        view_json = view_resp.json()
        if view_json.get("code") != 0:
            raise ValueError(f"Bilibili view API error: {view_json.get('message')}")

        data = view_json.get("data", {})
        title = data.get("title") or bvid
        cid = data.get("cid")
        pubdate = data.get("pubdate")
        duration = data.get("duration")
        if not cid:
            raise ValueError("Missing cid in Bilibili view data")

        play_api = (
            "https://api.bilibili.com/x/player/playurl"
            f"?bvid={bvid}&cid={cid}&qn=64&fnval=1"
        )
        play_resp = requests.get(play_api, headers=BILIBILI_HEADERS, timeout=20)
        play_resp.raise_for_status()
        play_json = play_resp.json()
        if play_json.get("code") != 0:
            raise ValueError(f"Bilibili play API error: {play_json.get('message')}")

        durl = (play_json.get("data") or {}).get("durl") or []
        if not durl:
            raise ValueError("No playable URL from Bilibili API")

        video_url = durl[0].get("url")
        if not video_url:
            raise ValueError("Missing video URL in Bilibili response")

        return VideoItem(
            input_value=value,
            title=title,
            source_url=video_url,
            video_id=bvid,
            local_video_path=None,
            local_audio_path=None,
            publish_timestamp=pubdate,
            duration_ms=duration * 1000 if isinstance(duration, int) else None,
            platform="bilibili",
            download_headers=BILIBILI_HEADERS,
        )
