from pathlib import Path
from typing import Any, Optional
import json
from http import HTTPStatus
from urllib import request

import dashscope
import os
from dashscope import MultiModalConversation
from openai import OpenAI
from openai import NotFoundError

from ...utils.retry import with_retry
from ...utils.text import clean_text
from ..models import Transcript


class DashScopeASRError(RuntimeError):
    def __init__(self, message: str, raw_response: dict | None = None):
        super().__init__(message)
        self.raw_response = raw_response


def _transcribe_with_openai(audio_path: Path, api_key: str, base_url: str, model: str) -> Transcript:
    client = OpenAI(api_key=api_key, base_url=base_url)

    def _call() -> Any:
        with audio_path.open("rb") as audio_file:
            return client.audio.transcriptions.create(
                model=model,
                file=audio_file,
            )

    response = with_retry(_call, retries=3, base_delay=1.0)
    raw = response.model_dump()
    text = clean_text(raw.get("text", ""))
    return Transcript(text=text, raw=raw)


def _transcribe_with_dashscope_url(source_url: str, api_key: str, model: str) -> Transcript:
    dashscope.api_key = api_key

    def _call() -> Transcript:
        task = dashscope.audio.asr.Transcription.async_call(
            model=model,
            file_urls=[source_url],
            language_hints=["zh", "en"],
        )
        transcription = dashscope.audio.asr.Transcription.wait(task=task.output.task_id)
        if transcription.status_code != HTTPStatus.OK:
            raise RuntimeError(f"DashScope ASR failed: {transcription.output.message}")

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


def transcribe_audio(
    audio_path: Optional[Path],
    source_url: Optional[str],
    api_key: str,
    base_url: str,
    model: str,
    mode: str = "auto",
    audio_asr_model: str | None = None,
) -> Transcript:
    mode = (mode or "auto").lower()
    if mode in ("dashscope-url", "auto") and source_url:
        return _transcribe_with_dashscope_url(source_url, api_key, model)

    if not audio_path:
        raise ValueError("audio_path is required for compatible ASR")

    if mode in ("audio-asr", "qwen-audio-asr"):
        if not audio_path:
            raise ValueError("audio_path is required for audio-asr")
        return _transcribe_with_qwen_audio_asr(
            audio_path=audio_path,
            api_key=api_key,
            model=audio_asr_model or "qwen-audio-asr",
        )

    try:
        return _transcribe_with_openai(audio_path, api_key, base_url, model)
    except NotFoundError:
        if mode == "auto" and source_url:
            return _transcribe_with_dashscope_url(source_url, api_key, model)
        raise



def _extract_multimodal_text(raw: dict) -> str:
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


def _transcribe_with_qwen_audio_asr(
    audio_path: Path,
    api_key: str,
    model: str,
) -> Transcript:
    dashscope.api_key = api_key
    audio_file_path = f"file://{audio_path.resolve()}"
    messages = [{"role": "user", "content": [{"audio": audio_file_path}]}]
    response = MultiModalConversation.call(model=model, messages=messages)
    raw = response.output if hasattr(response, "output") else response
    if hasattr(response, "status_code") and response.status_code != HTTPStatus.OK:
        raise DashScopeASRError(
            f"DashScope audio-asr failed: {response.message}",
            raw_response=getattr(response, "output", None),
        )
    text = _extract_multimodal_text({"output": raw})
    return Transcript(text=clean_text(text), raw=raw if isinstance(raw, dict) else {"output": raw})
