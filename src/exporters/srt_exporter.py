from pathlib import Path
from typing import Iterable

from ..pipeline.models import TaskResult


def _format_timestamp(ms: int) -> str:
    hours = ms // 3_600_000
    minutes = (ms % 3_600_000) // 60_000
    seconds = (ms % 60_000) // 1000
    millis = ms % 1000
    return f"{hours:02}:{minutes:02}:{seconds:02},{millis:03}"


def _build_srt(sentences: list[dict]) -> str:
    lines: list[str] = []
    for idx, sentence in enumerate(sentences, start=1):
        start_ms = int(sentence.get("begin_time", 0))
        end_ms = int(sentence.get("end_time", 0))
        text = sentence.get("text", "").strip()
        if not text:
            continue
        lines.append(str(idx))
        lines.append(f"{_format_timestamp(start_ms)} --> {_format_timestamp(end_ms)}")
        lines.append(text)
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def export_srt(results: Iterable[TaskResult], output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    srt_paths: list[Path] = []
    for idx, result in enumerate(results, start=1):
        raw = result.transcript.raw or {}
        transcripts = raw.get("transcripts") or []
        sentences = []
        if transcripts and isinstance(transcripts, list):
            sentences = transcripts[0].get("sentences") or []
        if not sentences:
            continue
        srt_text = _build_srt(sentences)
        srt_path = output_dir / f"video_{idx}.srt"
        srt_path.write_text(srt_text, encoding="utf-8")
        srt_paths.append(srt_path)
    return srt_paths
