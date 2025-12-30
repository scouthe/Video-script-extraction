import os
from dataclasses import dataclass
from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    api_key: str
    base_url: str
    asr_model: str
    llm_model: str
    asr_mode: str
    audio_asr_model: str


def get_settings() -> Settings:
    api_key = os.getenv("DASHSCOPE_API_KEY", "").strip()
    base_url = os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    asr_model = os.getenv("ASR_MODEL", "paraformer-v2")
    llm_model = os.getenv("LLM_MODEL", "qwen-plus")
    asr_mode = os.getenv("ASR_MODE", "auto")
    audio_asr_model = os.getenv("AUDIO_ASR_MODEL", "qwen-audio-asr")
    if not api_key:
        raise ValueError("Missing DASHSCOPE_API_KEY in environment or .env")
    return Settings(
        api_key=api_key,
        base_url=base_url,
        asr_model=asr_model,
        llm_model=llm_model,
        asr_mode=asr_mode,
        audio_asr_model=audio_asr_model,
    )
