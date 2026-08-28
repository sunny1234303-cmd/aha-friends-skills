import asyncio
import glob
import json
import os
import shutil
import uuid
from typing import List

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from recipe_pipeline import style_utils

from . import runner
from .models import RunRequest

app = FastAPI()

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
UPLOAD_DIR = os.path.expanduser("~/Movies/recipe_pipeline_uploads")
# 프로젝트 루트의 style-profiles/ — video-editing-style-analyzer 스킬이 여기에 쓴다
STYLE_PROFILES_DIR = os.environ.get(
    "RECIPE_STYLE_PROFILES_DIR",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "style-profiles"),
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/api/fonts")
def list_fonts():
    return style_utils.CAPTION_FONTS


@app.get("/api/style-profiles")
def list_style_profiles():
    out = []
    for path in sorted(glob.glob(os.path.join(STYLE_PROFILES_DIR, "*.json"))):
        name = os.path.splitext(os.path.basename(path))[0]
        prov = {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                prov = (json.load(f) or {}).get("provenance", {}) or {}
        except Exception:
            pass
        out.append(
            {
                "name": name,
                "channel_name": prov.get("channel_name"),
                "format": prov.get("format"),
                "analyzed_at": prov.get("analyzed_at"),
            }
        )
    return out


@app.get("/api/style-profiles/{name}")
def get_style_profile(name: str):
    path = os.path.join(STYLE_PROFILES_DIR, f"{os.path.basename(name)}.json")
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="style profile not found")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@app.post("/api/style-profiles")
def save_style_profile(profile: UploadFile = File(...)):
    os.makedirs(STYLE_PROFILES_DIR, exist_ok=True)
    name = os.path.basename(profile.filename or "profile.json")
    if not name.endswith(".json"):
        name += ".json"
    dest = os.path.join(STYLE_PROFILES_DIR, name)
    with open(dest, "wb") as f:
        shutil.copyfileobj(profile.file, f)
    return {"name": os.path.splitext(name)[0], "path": dest}


def _save_upload(upload: UploadFile, dest_dir: str) -> str:
    os.makedirs(dest_dir, exist_ok=True)
    dest_path = os.path.join(dest_dir, upload.filename)
    with open(dest_path, "wb") as f:
        shutil.copyfileobj(upload.file, f)
    return dest_path


@app.post("/api/runs")
def create_run(
    video: UploadFile = File(...),
    end_image: UploadFile = File(...),
    content_md: UploadFile = File(None),
    sfx: List[UploadFile] = File(None),
    style_profile: UploadFile = File(None),
    draft_name: str = Form(...),
    whisper_model_size: str = Form("small"),
    style_profile_name: str = Form(None),
    sfx_trigger: str = Form("keywords"),
    sfx_map: str = Form(""),
    target_duration_sec: float = Form(60.0),
    gap_threshold_sec: float = Form(0.6),
    pause_gap_sec: str = Form(""),
    max_cue_sec: str = Form(""),
    caption_font: str = Form("Arimo_Regular"),
    caption_size: float = Form(10.0),
    caption_color: str = Form("#FFFFFF"),
    caption_position: str = Form("bottom"),
    caption_all_caps: bool = Form(False),
    caption_outline_color: str = Form(""),
    caption_outline_width: float = Form(0.0),
    caption_shadow: bool = Form(False),
    caption_bg: bool = Form(False),
    caption_bg_color: str = Form("#000000"),
    caption_anim_in: str = Form("none"),
    caption_anim_out: str = Form("none"),
    caption_zoom_trigger: str = Form("keyword"),
    caption_zoom_scale: float = Form(1.15),
    overlay_font: str = Form("Arimo_Regular"),
    overlay_size: float = Form(7.0),
    overlay_color: str = Form("#FFEB99"),
    overlay_position: str = Form("top"),
    overlay_all_caps: bool = Form(False),
    overlay_outline_color: str = Form(""),
    overlay_outline_width: float = Form(0.0),
    overlay_bg: bool = Form(False),
    overlay_anim_in: str = Form("none"),
    overlay_anim_out: str = Form("none"),
    sfx_volume: float = Form(0.7),
):
    upload_dir = os.path.join(UPLOAD_DIR, uuid.uuid4().hex[:8])
    video_path = _save_upload(video, upload_dir)
    end_image_path = _save_upload(end_image, upload_dir)
    content_md_path = (
        _save_upload(content_md, upload_dir)
        if content_md is not None and content_md.filename
        else None
    )
    sfx_files = [s for s in (sfx or []) if s is not None and s.filename]
    sfx_path = sfx_dir = None
    if len(sfx_files) == 1:
        sfx_path = _save_upload(sfx_files[0], upload_dir)
    elif len(sfx_files) > 1:
        sfx_dir = os.path.join(upload_dir, "sfx")
        for s in sfx_files:
            _save_upload(s, sfx_dir)

    style_profile_path = None
    if style_profile is not None and style_profile.filename:
        saved = save_style_profile(style_profile)
        style_profile_path = saved["path"]
    elif style_profile_name:
        candidate = os.path.join(STYLE_PROFILES_DIR, f"{os.path.basename(style_profile_name)}.json")
        if os.path.isfile(candidate):
            style_profile_path = candidate

    request = RunRequest(
        video_path=video_path,
        content_md_path=content_md_path,
        end_image_path=end_image_path,
        draft_name=draft_name,
        whisper_model_size=whisper_model_size,
        style_profile_path=style_profile_path,
        target_duration_sec=target_duration_sec,
        gap_threshold_sec=gap_threshold_sec,
        pause_gap_sec=float(pause_gap_sec) if pause_gap_sec.strip() else None,
        max_cue_sec=float(max_cue_sec) if max_cue_sec.strip() else None,
        sfx_path=sfx_path,
        sfx_dir=sfx_dir,
        sfx_trigger=sfx_trigger,
        sfx_map=json.loads(sfx_map) if sfx_map.strip() else None,
        caption_font=caption_font,
        caption_size=caption_size,
        caption_color=caption_color,
        caption_position=caption_position,
        caption_all_caps=caption_all_caps,
        caption_outline_color=caption_outline_color or None,
        caption_outline_width=caption_outline_width,
        caption_shadow=caption_shadow,
        caption_bg=caption_bg,
        caption_bg_color=caption_bg_color,
        caption_anim_in=caption_anim_in,
        caption_anim_out=caption_anim_out,
        caption_zoom_trigger=caption_zoom_trigger,
        caption_zoom_scale=caption_zoom_scale,
        overlay_font=overlay_font,
        overlay_size=overlay_size,
        overlay_color=overlay_color,
        overlay_position=overlay_position,
        overlay_all_caps=overlay_all_caps,
        overlay_outline_color=overlay_outline_color or None,
        overlay_outline_width=overlay_outline_width,
        overlay_bg=overlay_bg,
        overlay_anim_in=overlay_anim_in,
        overlay_anim_out=overlay_anim_out,
        sfx_volume=sfx_volume,
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
