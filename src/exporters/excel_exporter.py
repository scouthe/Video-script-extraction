from pathlib import Path
from typing import Iterable

from openpyxl import Workbook
from datetime import datetime

from ..pipeline.models import TaskResult


HEADERS = ["序号", "视频标题", "链接", "发布时间", "时长", "文案", "摘要(可选)", "关键词(可选)"]


def export_excel(results: Iterable[TaskResult], output_path: Path) -> Path:
    wb = Workbook()
    ws = wb.active
    ws.title = "交付"

    ws.append(HEADERS)

    for idx, result in enumerate(results, start=1):
        publish_time = ""
        if result.item.publish_timestamp:
            ts = result.item.publish_timestamp
            if ts > 10**11:
                ts = int(ts / 1000)
            publish_time = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
        duration = ""
        if result.item.duration_ms:
            duration_value = result.item.duration_ms
            total_seconds = int(duration_value if duration_value < 1000 else duration_value / 1000)
            minutes = total_seconds // 60
            seconds = total_seconds % 60
            duration = f"{minutes:02}:{seconds:02}"
        ws.append(
            [
                idx,
                result.item.title,
                result.item.input_value or "",
                publish_time,
                duration,
                result.transcript.text,
                result.summary or "",
                "",
            ]
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
    return output_path
