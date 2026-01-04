from __future__ import annotations

from pathlib import Path
from typing import Any
import json
from http import HTTPStatus
from urllib import request
from tempfile import TemporaryDirectory

import dashscope
from dashscope import MultiModalConversation
from openai import OpenAI

from ..utils.retry import with_retry
from ..utils.text import clean_text
from ..utils.ffmpeg import split_audio
from ..pipeline.models import Transcript


class DashScopeASRError(RuntimeError):
    def __init__(self, message: str, raw_response: dict | None = None):
        super().__init__(message)
        self.raw_response = raw_response


class DashScopeUrlASR:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def transcribe(self, source_url: str, model: str) -> Transcript:
        dashscope.api_key = self.api_key

        def _call() -> Transcript:
            task = dashscope.audio.asr.Transcription.async_call(
                model=model,
                file_urls=[source_url],
                language_hints=["zh", "en"],
            )
            transcription = dashscope.audio.asr.Transcription.wait(task=task.output.task_id)
            if transcription.status_code != HTTPStatus.OK:
                raise DashScopeASRError(
                    f"DashScope ASR failed: {transcription.output.message}",
                    raw_response=transcription.output,
                )

            raw_output = transcription.output or {}
            if raw_output.get("task_status") == "FAILED":
                code = raw_output.get("code", "UNKNOWN")
                message = raw_output.get("message", "Task failed")
                raise DashScopeASRError(
                    f"DashScope ASR failed: {code} {message}",
                    raw_response=raw_output,
                )
            results = raw_output.get("results") or []
            if results and isinstance(results, list) and results[0].get("transcription_url"):
                result_url = results[0]["transcription_url"]
                raw = json.loads(request.urlopen(result_url).read().decode("utf-8"))
            else:
                raw = raw_output
            text = ""
            if "transcripts" in raw and raw["transcripts"]:
                text = raw["transcripts"][0].get("text", "")
            elif "text" in raw:
                text = raw.get("text", "")
            return Transcript(text=clean_text(text), raw=raw)

        return with_retry(_call, retries=3, base_delay=1.0)


class QwenAudioASR:
    def __init__(self, api_key: str, segment_seconds: int = 600) -> None:
        self.api_key = api_key
        self.segment_seconds = segment_seconds

    def _extract_multimodal_text(self, raw: dict) -> str:
        output = raw.get("output") or {}
        choices = output.get("choices") or []
        if choices:
            message = choices[0].get("message") or {}
            content = message.get("content")
            if isinstance(content, list):
                texts = [part.get("text", "") for part in content if isinstance(part, dict)]
                return " ".join([t for t in texts if t]).strip()
            if isinstance(content, str):
                return content.strip()
        if output.get("text"):
            return str(output.get("text")).strip()
        return ""

    def _transcribe_single(self, audio_path: Path, model: str) -> Transcript:
        dashscope.api_key = self.api_key
        audio_file_path = f"file://{audio_path.resolve()}"
        messages = [{"role": "user", "content": [{"audio": audio_file_path}]}]
        response = MultiModalConversation.call(model=model, messages=messages)
        raw = response.output if hasattr(response, "output") else response
        if hasattr(response, "status_code") and response.status_code != HTTPStatus.OK:
            raise DashScopeASRError(
                f"DashScope audio-asr failed: {response.message}",
                raw_response=getattr(response, "output", None),
            )
        text = self._extract_multimodal_text({"output": raw})
        return Transcript(text=clean_text(text), raw=raw if isinstance(raw, dict) else {"output": raw})

    def transcribe(self, audio_path: Path, model: str) -> Transcript:
        try:
            return self._transcribe_single(audio_path, model)
        except DashScopeASRError as exc:
            if "file size is too large" not in str(exc).lower():
                raise

        with TemporaryDirectory(prefix="audio_parts_") as tmp_dir:
            parts = split_audio(audio_path, Path(tmp_dir), segment_seconds=self.segment_seconds)
            if not parts:
                raise DashScopeASRError("Audio split produced no parts")
            texts: list[str] = []
            raw_parts: list[dict] = []
            for part in parts:
                part_transcript = self._transcribe_single(part, model)
                if part_transcript.text:
                    texts.append(part_transcript.text)
                raw_parts.append(part_transcript.raw if isinstance(part_transcript.raw, dict) else {})
            combined_text = clean_text("\n".join(texts))
            return Transcript(text=combined_text, raw={"parts": raw_parts})


class OpenAICompatibleASR:
    def __init__(self, api_key: str, base_url: str) -> None:
        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def transcribe(self, audio_path: Path, model: str) -> Transcript:
        def _call() -> Any:
            with audio_path.open("rb") as audio_file:
                return self.client.audio.transcriptions.create(
                    model=model,
                    file=audio_file,
                )

        response = with_retry(_call, retries=3, base_delay=1.0)
        raw = response.model_dump()
        text = clean_text(raw.get("text", ""))
        return Transcript(text=text, raw=raw)
