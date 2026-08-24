import asyncio
import json
import os
import shutil
import uuid

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from recipe_pipeline import style_utils

from . import runner
from .models import RunRequest

app = FastAPI()

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
UPLOAD_DIR = os.path.expanduser("~/Movies/recipe_pipeline_uploads")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/api/fonts")
def list_fonts():
    return style_utils.CAPTION_FONTS


def _save_upload(upload: UploadFile, dest_dir: str) -> str:
    os.makedirs(dest_dir, exist_ok=True)
    dest_path = os.path.join(dest_dir, upload.filename)
    with open(dest_path, "wb") as f:
        shutil.copyfileobj(upload.file, f)
    return dest_path


@app.post("/api/runs")
def create_run(
    video: UploadFile = File(...),
    content_md: UploadFile = File(...),
    end_image: UploadFile = File(...),
    sfx: UploadFile = File(None),
    draft_name: str = Form(...),
    whisper_model_size: str = Form("small"),
    target_duration_sec: float = Form(60.0),
    gap_threshold_sec: float = Form(0.6),
    caption_font: str = Form("Arimo_Regular"),
    caption_size: float = Form(10.0),
    caption_color: str = Form("#FFFFFF"),
    caption_position: str = Form("bottom"),
    overlay_font: str = Form("Arimo_Regular"),
    overlay_size: float = Form(7.0),
    overlay_color: str = Form("#FFEB99"),
    overlay_position: str = Form("top"),
):
    upload_dir = os.path.join(UPLOAD_DIR, uuid.uuid4().hex[:8])
    video_path = _save_upload(video, upload_dir)
    content_md_path = _save_upload(content_md, upload_dir)
    end_image_path = _save_upload(end_image, upload_dir)
    sfx_path = _save_upload(sfx, upload_dir) if sfx is not None and sfx.filename else None

    request = RunRequest(
        video_path=video_path,
        content_md_path=content_md_path,
        end_image_path=end_image_path,
        draft_name=draft_name,
        whisper_model_size=whisper_model_size,
        target_duration_sec=target_duration_sec,
        gap_threshold_sec=gap_threshold_sec,
        sfx_path=sfx_path,
        caption_font=caption_font,
        caption_size=caption_size,
        caption_color=caption_color,
        caption_position=caption_position,
        overlay_font=overlay_font,
        overlay_size=overlay_size,
        overlay_color=overlay_color,
        overlay_position=overlay_position,
    )
    run_id = runner.start_run(request)
    return {"run_id": run_id}


@app.get("/api/runs/{run_id}/status")
def run_status(run_id: str):
    try:
        state = runner.get_run(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="run not found")
    return json.loads(state.model_dump_json())


@app.get("/api/runs/{run_id}/events")
async def run_events(run_id: str):
    try:
        runner.get_run(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="run not found")

    async def event_stream():
        sent = 0
        while True:
            state = runner.get_run(run_id)
            while sent < len(state.stages):
                yield f"data: {state.stages[sent].model_dump_json()}\n\n"
                sent += 1
            if state.status != "running":
                yield f"event: done\ndata: {json.dumps({'status': state.status})}\n\n"
                break
            await asyncio.sleep(0.3)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/api/runs/{run_id}/summary")
def run_summary(run_id: str):
    try:
        state = runner.get_run(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="run not found")
    if state.status == "running":
        raise HTTPException(status_code=425, detail="run still in progress")
    if state.status == "error":
        raise HTTPException(status_code=500, detail=state.error)
    return json.loads(state.summary.model_dump_json())
