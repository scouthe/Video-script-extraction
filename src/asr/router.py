from __future__ import annotations

from pathlib import Path

from ..pipeline.models import VideoItem, Transcript
from ..config import Settings
from .providers import DashScopeUrlASR, QwenAudioASR, OpenAICompatibleASR


class ASRRouter:
    def __init__(
        self,
        dashscope_url_asr: DashScopeUrlASR,
        qwen_audio_asr: QwenAudioASR,
        openai_asr: OpenAICompatibleASR,
    ) -> None:
        self.dashscope_url_asr = dashscope_url_asr
        self.qwen_audio_asr = qwen_audio_asr
        self.openai_asr = openai_asr

    def select_mode(self, item: VideoItem, settings: Settings, use_source_url: bool) -> str:
        mode = (settings.asr_mode or "auto").lower()
        if use_source_url and mode in ("auto", "dashscope-url"):
            return "dashscope-url"
        if item.platform in ("bilibili", "local") or mode in ("audio-asr", "qwen-audio-asr"):
            return "audio-asr"
        return mode

    def transcribe(
        self,
        item: VideoItem,
        settings: Settings,
        use_source_url: bool,
    ) -> Transcript:
        selected_mode = self.select_mode(item, settings, use_source_url)
        if selected_mode == "dashscope-url":
            if not item.source_url:
                raise ValueError("source_url is required for dashscope-url")
            return self.dashscope_url_asr.transcribe(item.source_url, settings.asr_model)

        if selected_mode == "audio-asr":
            if not item.local_audio_path:
                raise ValueError("local_audio_path is required for audio-asr")
            return self.qwen_audio_asr.transcribe(item.local_audio_path, settings.audio_asr_model)

        if not item.local_audio_path:
            raise ValueError("local_audio_path is required for compatible ASR")
        return self.openai_asr.transcribe(item.local_audio_path, settings.asr_model)

    def describe_route(self, item: VideoItem, settings: Settings, use_source_url: bool) -> tuple[str, str, str]:
        selected_mode = self.select_mode(item, settings, use_source_url)
        if selected_mode == "dashscope-url":
            return selected_mode, settings.asr_model, "url"
        if selected_mode == "audio-asr":
            return selected_mode, settings.audio_asr_model, "local"
        return selected_mode, settings.asr_model, "local"
