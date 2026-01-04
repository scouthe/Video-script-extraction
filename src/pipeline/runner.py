from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Iterable

from ..config import Settings
from ..platforms.resolver import PlatformResolver
from ..asr.router import ASRRouter
from ..asr.providers import DashScopeUrlASR, QwenAudioASR, OpenAICompatibleASR
from .components import VideoDownloader, AudioExtractor, TextPostProcessor, Summarizer
from .models import TaskResult, Transcript
from ..utils.file import ensure_dir, hash_file


class PipelineRunner:
    def __init__(
        self,
        settings: Settings,
        platform_resolver: PlatformResolver,
        asr_router: ASRRouter,
        downloader: VideoDownloader,
        audio_extractor: AudioExtractor,
        post_processor: TextPostProcessor,
        summarizer: Summarizer,
    ) -> None:
        self.settings = settings
        self.platform_resolver = platform_resolver
        self.asr_router = asr_router
        self.downloader = downloader
        self.audio_extractor = audio_extractor
        self.post_processor = post_processor
        self.summarizer = summarizer

    def _cache_key(self, item) -> str:
        if item.video_id:
            return f"video_{item.video_id}"
        if item.local_audio_path and item.local_audio_path.exists():
            return f"audio_{hash_file(item.local_audio_path)}"
        if item.local_video_path and item.local_video_path.exists():
            return f"video_{hash_file(item.local_video_path)}"
        return f"input_{abs(hash(item.input_value))}"

    def run(
        self,
        inputs: Iterable[str],
        batch_name: str,
        output_root: Path,
        tmp_root: Path,
        enable_summary: bool = False,
        use_cache: bool = True,
        cache_dir: Path | None = None,
        on_progress=None,
        platform_hint: str | None = None,
    ) -> tuple[Path, list[TaskResult]]:
        date_prefix = datetime.now().strftime("%Y-%m-%d")
        output_dir = output_root / f"{date_prefix}_{batch_name}"
        ensure_dir(output_dir)
        ensure_dir(tmp_root)

        cache_dir = cache_dir or (output_root / ".cache")
        ensure_dir(cache_dir)

        results: list[TaskResult] = []
        inputs_list = list(inputs)
        total = len(inputs_list)
        print(
            "[pipeline] inputs="
            + str(total)
            + " batch="
            + batch_name
            + " platform="
            + str(platform_hint)
            + " asr_mode="
            + self.settings.asr_mode
            + " asr_model="
            + self.settings.asr_model
            + " audio_asr_model="
            + self.settings.audio_asr_model
        )

        for idx, value in enumerate(inputs_list, start=1):
            if on_progress:
                on_progress(step="parse", current=idx, total=total, message="解析输入")
            item = self.platform_resolver.resolve(value, platform_hint)
            use_source_url = (
                self.settings.asr_mode in ("dashscope-url", "auto")
                and item.source_url
                and item.platform == "douyin"
            )
            print(
                "[pipeline] item "
                + str(idx)
                + " platform="
                + item.platform
                + " use_source_url="
                + str(use_source_url)
                + " source_url="
                + ("yes" if item.source_url else "no")
            )

            if not use_source_url:
                if on_progress:
                    on_progress(step="download", current=idx, total=total, message="下载视频")
                item = self.downloader.download(item, tmp_root)
                if on_progress:
                    on_progress(step="audio", current=idx, total=total, message="抽取音频")
                item = self.audio_extractor.extract(item, tmp_root)

            cache_key = self._cache_key(item)
            cache_path = cache_dir / f"{cache_key}.json"
            if use_cache and cache_path.exists():
                raw = json.loads(cache_path.read_text(encoding="utf-8"))
                text = raw.get("text", "")
            else:
                if on_progress:
                    on_progress(step="asr", current=idx, total=total, message="语音识别")
                mode, model, route = self.asr_router.describe_route(item, self.settings, use_source_url)
                print(
                    "[pipeline] asr_mode_selected="
                    + mode
                    + " model="
                    + model
                    + " route="
                    + route
                )
                transcript = self.asr_router.transcribe(item, self.settings, use_source_url)
                raw = transcript.raw
                text = transcript.text
                cache_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")

            if on_progress:
                on_progress(step="postprocess", current=idx, total=total, message="文本后处理")
            paragraphs = self.post_processor.process(text)
            summary = None
            if enable_summary and text:
                if on_progress:
                    on_progress(step="summary", current=idx, total=total, message="生成摘要")
                summary = self.summarizer.summarize(
                    text=text,
                    api_key=self.settings.api_key,
                    base_url=self.settings.base_url,
                    model=self.settings.llm_model,
                )

            raw_out_path = output_dir / f"raw_{idx}.json"
            raw_out_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")

            results.append(
                TaskResult(
                    item=item,
                    transcript=Transcript(text="\n".join(paragraphs), raw=raw),
                    summary=summary,
                )
            )

        return output_dir, results


class PipelineFactory:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def create(self) -> PipelineRunner:
        platform_resolver = PlatformResolver()
        asr_router = ASRRouter(
            dashscope_url_asr=DashScopeUrlASR(self.settings.api_key),
            qwen_audio_asr=QwenAudioASR(self.settings.api_key),
            openai_asr=OpenAICompatibleASR(self.settings.api_key, self.settings.base_url),
        )
        return PipelineRunner(
            settings=self.settings,
            platform_resolver=platform_resolver,
            asr_router=asr_router,
            downloader=VideoDownloader(),
            audio_extractor=AudioExtractor(),
            post_processor=TextPostProcessor(),
            summarizer=Summarizer(),
        )
