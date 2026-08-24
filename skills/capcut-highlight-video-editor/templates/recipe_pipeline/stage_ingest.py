"""Stage 1: 영상 삽입.

Also stages all input media (source video, end image, SFX audio) into a
folder CapCut's macOS sandbox can actually read. Confirmed via manual testing
(Milestone 0 spike + Milestone 1 first real run): CapCut on macOS fails to
resolve media referenced from arbitrary paths (e.g. under the workspace repo)
with a "미디어 연결" (media not found) dialog, even though the JSON path is
correct and absolute — but the same file under ~/Movies resolves fine. So any
media path handed to pycapcut must first be copied under a CapCut-readable
folder (default: ~/Movies/recipe_pipeline_media/); the pipeline never
modifies the user's original source files, only copies them.
"""

import os
import shutil

DEFAULT_STAGING_DIR = os.path.expanduser("~/Movies/recipe_pipeline_media")


def stage_media_file(path: str, staging_dir: str = DEFAULT_STAGING_DIR) -> str:
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    os.makedirs(staging_dir, exist_ok=True)
    dest = os.path.join(staging_dir, os.path.basename(path))
    if os.path.abspath(dest) != os.path.abspath(path):
        shutil.copyfile(path, dest)
    return dest
