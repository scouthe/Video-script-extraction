from pathlib import Path
import shutil
import ffmpeg


def _ensure_ffmpeg() -> None:
    if not shutil.which("ffmpeg"):
        raise FileNotFoundError(
            "ffmpeg not found in PATH. Install ffmpeg and ensure it is available in PATH."
        )


def extract_audio(video_path: Path, audio_path: Path) -> Path:
    _ensure_ffmpeg()
    (
        ffmpeg
        .input(str(video_path))
        .output(
            str(audio_path),
            ac=1,
            ar=16000,
            acodec="pcm_s16le",
        )
        .run(capture_stdout=True, capture_stderr=True, overwrite_output=True)
    )
    return audio_path
