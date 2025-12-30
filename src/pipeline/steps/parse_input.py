import json
import re
from pathlib import Path
from typing import Optional

import requests

from ..models import VideoItem


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) EdgiOS/121.0.2277.107 "
        "Version/17.0 Mobile/15E148 Safari/604.1"
    )
}

BILIBILI_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.bilibili.com/",
}


def _extract_first_url(text: str) -> Optional[str]:
    urls = re.findall(
        r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|"
        r"(?:%[0-9a-fA-F][0-9a-fA-F]))+",
        text,
    )
    return urls[0] if urls else None


def parse_share_url(share_text: str) -> dict:
    share_url = _extract_first_url(share_text)
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

    return {
        "url": video_url,
        "title": desc,
        "video_id": video_id,
        "create_time": create_time,
        "duration_ms": duration_ms,
    }


def _resolve_bilibili_url(value: str) -> str:
    if value.startswith("http://") or value.startswith("https://"):
        resp = requests.get(value, headers=BILIBILI_HEADERS, timeout=20, allow_redirects=True)
        resp.raise_for_status()
        return resp.url
    return value


def parse_bilibili_url(value: str) -> dict:
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

    return {
        "url": video_url,
        "title": title,
        "video_id": bvid,
        "create_time": pubdate,
        "duration_ms": duration * 1000 if isinstance(duration, int) else None,
        "download_headers": BILIBILI_HEADERS,
    }


def parse_input_item(value: str, platform: str | None = None) -> VideoItem:
    path = Path(value)
    if path.exists() and path.is_file():
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

    platform = (platform or "auto").lower()
    if platform == "bilibili" or "bilibili.com" in value or "b23.tv" in value:
        video_info = parse_bilibili_url(value)
        return VideoItem(
            input_value=value,
            title=video_info["title"],
            source_url=video_info["url"],
            video_id=video_info["video_id"],
            local_video_path=None,
            local_audio_path=None,
            publish_timestamp=video_info.get("create_time"),
            duration_ms=video_info.get("duration_ms"),
            platform="bilibili",
            download_headers=video_info.get("download_headers"),
        )

    video_info = parse_share_url(value)
    return VideoItem(
        input_value=value,
        title=video_info["title"],
        source_url=video_info["url"],
        video_id=video_info["video_id"],
        local_video_path=None,
        local_audio_path=None,
        publish_timestamp=video_info.get("create_time"),
        duration_ms=video_info.get("duration_ms"),
        platform="douyin",
        download_headers=HEADERS,
    )
