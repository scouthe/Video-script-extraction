from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List
import queue
import threading
import uuid
import traceback

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from ..config import get_settings
from ..pipeline.runner import PipelineFactory
from ..exporters.word_exporter import export_word
from ..exporters.excel_exporter import export_excel
from ..exporters.srt_exporter import export_srt
from ..utils.file import sanitize_filename
from ..collectors.douyin_profile import collect_profile_links_async


BASE_DIR = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(BASE_DIR / "templates"))
STATIC_DIR = BASE_DIR / "static"
OUTPUT_ROOT = Path("outputs")
TMP_ROOT = Path("tmp")


app = FastAPI(title="Douyin Delivery Tool")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

JOB_QUEUE: "queue.Queue[str]" = queue.Queue()
JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()


def _update_job(job_id: str, **updates) -> None:
    with JOBS_LOCK:
        job = JOBS.get(job_id, {})
        job.update(updates)
        JOBS[job_id] = job


def _worker() -> None:
    while True:
        job_id = JOB_QUEUE.get()
        job = JOBS.get(job_id)
        if not job:
            JOB_QUEUE.task_done()
            continue
        _update_job(job_id, status="running")
        try:
            settings = get_settings()

            def _progress(step: str, current: int, total: int, message: str) -> None:
                _update_job(
                    job_id,
                    progress={
                        "step": step,
                        "current": current,
                        "total": total,
                        "message": message,
                    },
                )

            runner = PipelineFactory(settings).create()
            output_dir, results = runner.run(
                inputs=job["inputs"],
                batch_name=job["name"],
                output_root=OUTPUT_ROOT,
                tmp_root=TMP_ROOT,
                enable_summary=job["summary"],
                use_cache=True,
                on_progress=_progress,
                platform_hint=job.get("platform"),
            )

            exports: list[str] = []
            if not job["export_docx"] and not job["export_xlsx"] and not job["export_srt"]:
                job["export_docx"] = True
            safe_name = sanitize_filename(job["name"]) or "delivery"
            if job["export_docx"]:
                filename = f"{safe_name}.docx"
                export_word(results, output_dir / filename, job["name"])
                exports.append(filename)
            if job["export_xlsx"]:
                filename = f"{safe_name}.xlsx"
                export_excel(results, output_dir / filename)
                exports.append(filename)
            if job["export_srt"]:
                srt_paths = export_srt(results, output_dir)
                exports.extend([p.name for p in srt_paths])

            _update_job(
                job_id,
                status="done",
                output_dir=output_dir.name,
                exports=exports,
                progress={
                    "step": "done",
                    "current": len(job["inputs"]),
                    "total": len(job["inputs"]),
                    "message": "任务完成",
                },
                finished_at=datetime.now().isoformat(),
            )
        except Exception as exc:
            _update_job(
                job_id,
                status="error",
                error=str(exc),
                error_detail=traceback.format_exc(),
                error_raw=getattr(exc, "raw_response", None),
                progress={
                    "step": "error",
                    "current": 0,
                    "total": len(job["inputs"]),
                    "message": "任务失败",
                },
            )
        finally:
            JOB_QUEUE.task_done()


@app.on_event("startup")
def _start_worker() -> None:
    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return TEMPLATES.TemplateResponse("index.html", {"request": request})


@app.get("/history", response_class=HTMLResponse)
def history(request: Request) -> HTMLResponse:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    batches = []
    for path in sorted(OUTPUT_ROOT.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not path.is_dir():
            continue
        files = [p.name for p in path.iterdir() if p.is_file()]
        batches.append({"name": path.name, "files": files})
    return TEMPLATES.TemplateResponse(
        "history.html",
        {"request": request, "batches": batches},
    )


@app.post("/run", response_class=HTMLResponse)
async def run_delivery(
    request: Request,
    name: str = Form(...),
    links: str = Form(""),
    uid: str = Form(""),
    platform: str = Form("auto"),
    count: int = Form(0),
    files: List[UploadFile] | None = File(None),
    export_docx: bool = Form(False),
    export_xlsx: bool = Form(False),
    export_srt: bool = Form(False),
    summary: bool = Form(False),
) -> HTMLResponse:
    inputs: list[str] = []
    if links.strip():
        inputs.extend([line.strip() for line in links.splitlines() if line.strip()])
    if uid.strip():
        try:
            result = await collect_profile_links_async(uid.strip(), limit=count)
            if result.links:
                inputs.extend(result.links)
            else:
                return TEMPLATES.TemplateResponse(
                    "index.html",
                    {"request": request, "error": "未采集到任何公开视频链接，请确认 UID/主页链接有效。"},
                )
        except Exception as exc:
            return TEMPLATES.TemplateResponse(
                "index.html",
                {"request": request, "error": f"采集账号视频失败: {exc}"},
            )

    if files:
        for upload in files:
            if not upload.filename:
                continue
            suffix = Path(upload.filename).suffix
            safe_name = upload.filename.replace("/", "_").replace("\\", "_")
            tmp_name = f"upload_{datetime.now().timestamp():.0f}_{safe_name}"
            if suffix:
                tmp_name = f"{Path(tmp_name).stem}{suffix}"
            tmp_path = TMP_ROOT / tmp_name
            TMP_ROOT.mkdir(parents=True, exist_ok=True)
            with tmp_path.open("wb") as f:
                f.write(await upload.read())
            inputs.append(str(tmp_path))

    if not inputs:
        return TEMPLATES.TemplateResponse(
            "index.html",
            {"request": request, "error": "请至少输入链接或上传文件。"},
        )

    job_id = str(uuid.uuid4())
    _update_job(
        job_id,
        status="queued",
        name=name,
        inputs=inputs,
        platform=platform,
        export_docx=export_docx,
        export_xlsx=export_xlsx,
        export_srt=export_srt,
        summary=summary,
        created_at=datetime.now().isoformat(),
        progress={"step": "queued", "current": 0, "total": len(inputs), "message": "排队中"},
    )
    JOB_QUEUE.put(job_id)

    return TEMPLATES.TemplateResponse(
        "progress.html",
        {"request": request, "job_id": job_id},
    )


@app.get("/api/jobs/{job_id}", response_class=JSONResponse)
def job_status(job_id: str) -> JSONResponse:
    job = JOBS.get(job_id)
    if not job:
        return JSONResponse({"status": "not_found"}, status_code=404)
    return JSONResponse(job)


@app.get("/download/{batch}/{filename}")
def download_file(batch: str, filename: str) -> FileResponse:
    file_path = (OUTPUT_ROOT / batch / filename).resolve()
    root = OUTPUT_ROOT.resolve()
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    if not file_path.is_relative_to(root):
        raise HTTPException(status_code=400, detail="Invalid path")
    return FileResponse(path=file_path, filename=filename)
