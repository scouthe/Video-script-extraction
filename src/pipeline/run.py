import json
from datetime import datetime
from pathlib import Path
from typing import Iterable

from .models import TaskResult, Transcript
from .steps.parse_input import parse_input_item
from .steps.download import download_video
from .steps.extract_audio import extract_audio
from .steps.asr_dashscope import transcribe_audio
from .steps.postprocess import postprocess_text
from .steps.enrich_llm import summarize_text
from ..utils.file import ensure_dir, hash_file


def _cache_key(item) -> str:
    if item.video_id:
        return f"video_{item.video_id}"
    if item.local_audio_path and item.local_audio_path.exists():
        return f"audio_{hash_file(item.local_audio_path)}"
    if item.local_video_path and item.local_video_path.exists():
        return f"video_{hash_file(item.local_video_path)}"
    return f"input_{abs(hash(item.input_value))}"


def run_pipeline(
    inputs: Iterable[str],
    settings,
    batch_name: str,
    output_root: Path,
    tmp_root: Path,
    enable_summary: bool = False,
    use_cache: bool = True,
    cache_dir: Path | None = None,
    on_progress=None,
    platform: str | None = None,
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
    for idx, value in enumerate(inputs_list, start=1):
        if on_progress:
            on_progress(step="parse", current=idx, total=total, message="解析输入")
        item = parse_input_item(value, platform=platform)
        use_source_url = (
            settings.asr_mode in ("dashscope-url", "auto")
            and item.source_url
            and item.platform == "douyin"
        )
        if not use_source_url:
            if on_progress:
                on_progress(step="download", current=idx, total=total, message="下载视频")
            item = download_video(item, tmp_root)
            if on_progress:
                on_progress(step="audio", current=idx, total=total, message="抽取音频")
            item = extract_audio(item, tmp_root)

        cache_key = _cache_key(item)
        cache_path = cache_dir / f"{cache_key}.json"
        if use_cache and cache_path.exists():
            raw = json.loads(cache_path.read_text(encoding="utf-8"))
            text = raw.get("text", "")
        else:
            if on_progress:
                on_progress(step="asr", current=idx, total=total, message="语音识别")
            mode = settings.asr_mode
            if item.platform in ("bilibili", "local"):
                mode = "audio-asr"
            transcript = transcribe_audio(
                audio_path=item.local_audio_path,
                source_url=item.source_url if use_source_url else None,
                api_key=settings.api_key,
                base_url=settings.base_url,
                model=settings.asr_model,
                mode=mode,
                audio_asr_model=settings.audio_asr_model,
            )
            raw = transcript.raw
            text = transcript.text
            cache_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")

        if on_progress:
            on_progress(step="postprocess", current=idx, total=total, message="文本后处理")
        paragraphs = postprocess_text(text)
        summary = None
        if enable_summary and text:
            if on_progress:
                on_progress(step="summary", current=idx, total=total, message="生成摘要")
            summary = summarize_text(
                text=text,
                api_key=settings.api_key,
                base_url=settings.base_url,
                model=settings.llm_model,
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
