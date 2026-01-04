from pathlib import Path
from typing import Iterable

from ..config import Settings
from .runner import PipelineFactory


def run_pipeline(
    inputs: Iterable[str],
    settings: Settings,
    batch_name: str,
    output_root: Path,
    tmp_root: Path,
    enable_summary: bool = False,
    use_cache: bool = True,
    cache_dir: Path | None = None,
    on_progress=None,
    platform: str | None = None,
) -> tuple[Path, list]:
    runner = PipelineFactory(settings).create()
    return runner.run(
        inputs=inputs,
        batch_name=batch_name,
        output_root=output_root,
        tmp_root=tmp_root,
        enable_summary=enable_summary,
        use_cache=use_cache,
        cache_dir=cache_dir,
        on_progress=on_progress,
        platform_hint=platform,
    )
