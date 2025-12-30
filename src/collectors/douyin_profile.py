from __future__ import annotations

from dataclasses import dataclass
import re

from playwright.sync_api import sync_playwright
from playwright.async_api import async_playwright


@dataclass
class ProfileCollectResult:
    links: list[str]
    scanned: int


def _normalize_profile_url(uid_or_url: str) -> str:
    if uid_or_url.startswith("http://") or uid_or_url.startswith("https://"):
        return uid_or_url
    return f"https://www.douyin.com/user/{uid_or_url}"


def collect_profile_links(
    uid_or_url: str,
    limit: int = 0,
    timeout_ms: int = 120_000,
) -> ProfileCollectResult:
    url = _normalize_profile_url(uid_or_url)
    links: list[str] = []
    seen = set()
    target = limit if limit and limit > 0 else None

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            )
        )
        page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)

    stagnation = 0
    while True:
        previous_height = page.evaluate("document.body.scrollHeight")
        page.mouse.wheel(0, 4000)
        page.wait_for_timeout(1200)
        current_height = page.evaluate("document.body.scrollHeight")
        if current_height == previous_height:
            stagnation += 1
        else:
            stagnation = 0
        if stagnation >= 3:
            break

    html = page.content()
    matches = re.findall(r'href="([^"]*?/video/[^"]+)"', html)
    for href in matches:
        full = href if href.startswith("http") else f"https://www.douyin.com{href}"
        if full not in seen:
            seen.add(full)
            links.append(full)
        if target and len(links) >= target:
            links = links[:target]
            break

        browser.close()

    return ProfileCollectResult(links=links, scanned=len(links))


async def collect_profile_links_async(
    uid_or_url: str,
    limit: int = 0,
    timeout_ms: int = 120_000,
) -> ProfileCollectResult:
    url = _normalize_profile_url(uid_or_url)
    links: list[str] = []
    seen = set()
    target = limit if limit and limit > 0 else None

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            )
        )
        await page.route("**/*", lambda route: route.abort() if route.request.resource_type in {"image", "media", "font"} else route.continue_())
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        except Exception:
            await page.goto(url, wait_until="load", timeout=timeout_ms)

        stagnation = 0
        while True:
            previous_height = await page.evaluate("document.body.scrollHeight")
            await page.mouse.wheel(0, 4000)
            await page.wait_for_timeout(1200)
            current_height = await page.evaluate("document.body.scrollHeight")
            if current_height == previous_height:
                stagnation += 1
            else:
                stagnation = 0
            if stagnation >= 3:
                break

        html = await page.content()
        matches = re.findall(r'href="([^"]*?/video/[^"]+)"', html)
        for href in matches:
            full = href if href.startswith("http") else f"https://www.douyin.com{href}"
            if full not in seen:
                seen.add(full)
                links.append(full)
            if target and len(links) >= target:
                links = links[:target]
                break

        await browser.close()

    return ProfileCollectResult(links=links, scanned=len(links))
