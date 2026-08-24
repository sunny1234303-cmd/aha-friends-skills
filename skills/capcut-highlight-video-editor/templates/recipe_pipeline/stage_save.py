"""Stage 10: 사용자 최종 확인 및 수정을 위한 클립 삭제 가능한 상태로 프로그램 저장.

Saves the draft (no render/export). Two macOS-CapCut-specific fixes, both
confirmed via manual testing (see spike/NOTES.md and MILESTONE1_NOTES.md):

1. Copies draft_content.json to draft_info.json in the same folder — macOS
   CapCut reads draft_info.json, not draft_content.json (the Windows
   filename pycapcut writes). Without this, the draft shows up in CapCut's
   project list but opens to an empty timeline.

2. Syncs the cached `draft_id` in root_meta_info.json (CapCut's project-list
   index) to match the id pycapcut just generated in draft_info.json. When a
   draft with this name already existed and pipeline.py deleted+recreated its
   folder (see the stale-cache handling in pipeline.py), pycapcut assigns a
   brand new random id — but CapCut's list still has the *old* id cached from
   before. Clicking the list entry then silently does nothing (confirmed:
   CapCut tries to open by the stale id, finds no match, no error shown).
"""

import json
import os
import shutil

import pycapcut as cc


def save_editable_draft(
    draft_folder: str, draft_name: str, script: cc.ScriptFile
) -> str:
    script.save()
    draft_dir = os.path.join(draft_folder, draft_name)
    content_path = os.path.join(draft_dir, "draft_content.json")
    info_path = os.path.join(draft_dir, "draft_info.json")
    shutil.copyfile(content_path, info_path)

    _sync_root_meta_info(draft_folder, draft_name, info_path)

    return draft_dir


def _sync_root_meta_info(draft_folder: str, draft_name: str, info_path: str) -> None:
    root_meta_path = os.path.join(draft_folder, "root_meta_info.json")
    if not os.path.exists(root_meta_path):
        return  # first-ever draft in this folder — CapCut creates the index itself

    with open(info_path, encoding="utf-8") as f:
        info = json.load(f)

    with open(root_meta_path, encoding="utf-8") as f:
        root_meta = json.load(f)

    changed = False
    for entry in root_meta.get("all_draft_store", []):
        if entry.get("draft_name") == draft_name:
            entry["draft_id"] = info["id"]
            entry["tm_duration"] = info["duration"]
            changed = True

    if changed:
        with open(root_meta_path, "w", encoding="utf-8") as f:
            json.dump(root_meta, f, ensure_ascii=False)
