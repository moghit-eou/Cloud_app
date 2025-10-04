from pathlib import Path
from functools import lru_cache
import json

CONFIG_PATH = Path(__file__).with_name("file_types.json")

@lru_cache(maxsize=1)
def _cfg():
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)

def file_category(file_obj):
    cfg = _cfg()
    name = (file_obj.get("name") or "").lower()
    mime = file_obj.get("mimeType") or ""

    # Google native
    gmap = cfg.get("_google_to_category", {})
    if mime in gmap:
        return gmap[mime]

    # Config-driven
    for cat, rules in cfg.items():
        if cat.startswith("_"):
            continue
        mimes = set(rules.get("mimes", []))
        exts = tuple((rules.get("ext") or []))
        if mime in mimes or (exts and name.endswith(exts)):
            return cat

    # Generic fallback
    if mime.startswith("image/"): return "image"
    if mime.startswith("video/"): return "video"
    if mime.startswith("audio/"): return "audio"
    if mime.startswith("text/"):  return "text"
    return "other"

def annotate_files(files):
    for f in files:
        if f.get("mimeType") != "application/vnd.google-apps.folder":
            f["category"] = file_category(f)
    return files

def filter_and_sort(files, wanted_type="all", sort_by="name"):
    wanted = (wanted_type or "all").lower()
    if wanted != "all":
        files = [f for f in files if f.get("category") == wanted]

    key = (sort_by or "name").lower()
    if key == "type":
        files.sort(key=lambda x: (x.get("category","other"), x.get("name","").lower()))
    else:
        files.sort(key=lambda x: x.get("name","").lower())
    return files
