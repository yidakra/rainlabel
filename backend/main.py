from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import json
from typing import List, Dict, Any, Optional
from pathlib import Path
import logging
import time
from collections import deque
import os
import re
import uuid

app = FastAPI(title="RainLabel Video Analysis API", version="1.0.0")

# Logger for audit and security events
logger = logging.getLogger(__name__)

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],  # React dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Basic request limits
MAX_MULTIPART_SIZE = int(os.getenv("RAINLABEL_MAX_MULTIPART_SIZE", str(50 * 1024 * 1024)))  # 50 MiB default
RATE_LIMIT_PER_MINUTE = int(os.getenv("RAINLABEL_RATE_LIMIT_PER_MINUTE", "120"))

_ip_windows: Dict[str, deque] = {}

@app.middleware("http")
async def _limits_middleware(request, call_next):
    # Per-IP sliding window (60s)
    now = time.monotonic()
    client_ip = (request.headers.get("x-forwarded-for", "").split(",")[0].strip() or
                 getattr(getattr(request, "client", None), "host", "unknown"))
    window = _ip_windows.setdefault(client_ip, deque())
    cutoff = now - 60.0
    while window and window[0] < cutoff:
        window.popleft()
    if len(window) >= RATE_LIMIT_PER_MINUTE:
        return JSONResponse({"detail": "Too Many Requests"}, status_code=429)
    window.append(now)

    # Multipart max size guard via Content-Length
    ctype = request.headers.get("content-type", "").lower()
    if "multipart/form-data" in ctype:
        try:
            content_length = int(request.headers.get("content-length", "0"))
        except Exception:
            content_length = 0
        if content_length and content_length > MAX_MULTIPART_SIZE:
            return JSONResponse({"detail": "Payload too large"}, status_code=413)
    return await call_next(request)

# Resolve project root regardless of current working directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Mount static files
VIDEOS_DIR = BASE_DIR / "videos"

# Supported video extensions
VIDEO_EXTENSIONS = ['.mp4', '.avi', '.mov', '.mkv', '.webm']


def _is_child_path(child: Path, parent: Path) -> bool:
    """Return True if child is inside parent after resolution."""
    try:
        return child.is_relative_to(parent)  # type: ignore[attr-defined]
    except Exception:
        parent_posix = parent.as_posix().rstrip("/") + "/"
        return child.as_posix().startswith(parent_posix)


def find_metadata_path(stem: str) -> Optional[Path]:
    """Locate metadata sidecar for a given video stem under `videos/` only.

    Returns a Path if found, otherwise None. Includes basic input validation and
    containment checks to avoid path traversal.
    """
    if not stem:
        return None
    separators = {"/", "\\", os.sep}
    if os.altsep:
        separators.add(os.altsep)
    if "\x00" in stem or any(sep in stem for sep in separators):
        return None
    valid = False
    try:
        uuid.UUID(stem)
        valid = True
    except Exception:
        valid = bool(re.fullmatch(r"^[A-Za-z0-9_-]+$", stem))
    if not valid:
        return None

    # sidecar next to any matching video file
    for ext in VIDEO_EXTENSIONS:
        vp = (VIDEOS_DIR / f"{stem}{ext}").resolve()
        if vp.exists() and _is_child_path(vp, VIDEOS_DIR.resolve()):
            sidecar = Path(str(vp) + ".json").resolve()
            if sidecar.exists() and _is_child_path(sidecar, VIDEOS_DIR.resolve()):
                return sidecar
    return None

def has_metadata_for(stem: str) -> bool:
    """Return True if any metadata exists for the given video stem."""
    return find_metadata_path(stem) is not None

# Ensure directory exists
VIDEOS_DIR.mkdir(exist_ok=True)

if VIDEOS_DIR.exists():
    app.mount("/static/videos", StaticFiles(directory=VIDEOS_DIR), name="videos")

@app.get("/")
async def root():
    return {"message": "RainLabel Video Analysis API"}

@app.get("/videos")
async def get_videos() -> List[Dict[str, Any]]:
    """Get list of all available videos"""
    videos = []
    
    if not VIDEOS_DIR.exists():
        return videos

    for video_file in VIDEOS_DIR.iterdir():
        if video_file.is_file() and video_file.suffix.lower() in VIDEO_EXTENSIONS:
            try:
                file_size = video_file.stat().st_size
            except Exception:
                continue
            if file_size <= 0:
                # Skip zero-byte or unreadable files
                continue
            video_info = {
                "name": video_file.stem,
                "filename": video_file.name,
                "path": f"/static/videos/{video_file.name}",
                "size": file_size,
                "has_metadata": has_metadata_for(video_file.stem)
            }
            videos.append(video_info)
    
    return videos

@app.get("/video/{video_name}")
async def get_video(video_name: str) -> Dict[str, Any]:
    """Get specific video information"""
    
    for ext in VIDEO_EXTENSIONS:
        video_path = VIDEOS_DIR / f"{video_name}{ext}"
        if video_path.exists():
            return {
                "name": video_name,
                "filename": video_path.name,
                "path": f"/static/videos/{video_path.name}",
                "size": video_path.stat().st_size,
                "has_metadata": has_metadata_for(video_name)
            }
    
    raise HTTPException(status_code=404, detail="Video not found")

@app.get("/metadata/{video_name}")
async def get_metadata(video_name: str) -> Dict[str, Any]:
    """Get video analysis metadata"""
    # 1) Validate and canonicalize the input at the boundary
    sanitized = (video_name or "").strip()
    separators = {"/", "\\", os.sep}
    if os.altsep:
        separators.add(os.altsep)
    if "\x00" in sanitized or any(sep in sanitized for sep in separators):
        logger.warning("Rejected video_name with path separators or NUL byte: %r", video_name)
        raise HTTPException(status_code=400, detail="Invalid video name")

    is_uuid = False
    try:
        uuid.UUID(sanitized)
        is_uuid = True
    except Exception:
        is_uuid = False

    if not is_uuid and not re.fullmatch(r"^[A-Za-z0-9_-]+$", sanitized):
        logger.warning("Rejected video_name not matching allow-list regex/UUID: %r", video_name)
        raise HTTPException(status_code=400, detail="Invalid video name")

    # 2) Authorization check (env-driven allow-list; default allow all)
    allowed_env = os.getenv("RAINLABEL_ALLOWED_VIDEOS")
    if allowed_env is not None:
        allowed_set = {v.strip() for v in allowed_env.split(",") if v.strip()}
        if sanitized not in allowed_set:
            logger.warning("Forbidden access to video_name not in allow-list: %r", sanitized)
            raise HTTPException(status_code=403, detail="Forbidden")

    # Use sanitized name going forward
    video_name = sanitized
    metadata_path = find_metadata_path(video_name)

    if metadata_path is None or not metadata_path.exists():
        # Return sample metadata structure if no real metadata exists
        return {
            "video_name": video_name,
            "labels": [],
            "shots": [],
            "objects": [],
            "text": [],
            "faces": [],
            "message": "No analysis data available. This is sample structure."
        }
    
    try:
        with open(metadata_path, 'r') as f:
            raw = json.load(f)
        # If the file is already in the expected schema, return as-is
        if "labels" in raw and any(isinstance(x, dict) and "segments" in x for x in raw.get("labels", [])):
            return raw
        # Transform new analyzer output schema into frontend-expected structure
        transformed: Dict[str, Any] = {
            "video_name": raw.get("video_name") or raw.get("video_file", video_name),
            "labels": [],
            "shots": raw.get("shots", []),
            "objects": raw.get("objects", []),
            "text": raw.get("text", []),
            "faces": raw.get("faces", []),
        }
        flat_labels = raw.get("labels", [])
        grouped: Dict[str, Dict[str, Any]] = {}
        for item in flat_labels:
            desc = item.get("description") or item.get("entity") or "Unknown"
            start_time = item.get("start_time")
            end_time = item.get("end_time")
            conf = item.get("confidence", 0.0)
            cats = item.get("category") or item.get("categories") or []
            if desc not in grouped:
                grouped[desc] = {
                    "description": desc,
                    "confidence": conf,
                    "categories": list({c for c in cats if c}),
                    "segments": [],
                }
            # Update representative confidence to max and merge categories
            grouped[desc]["confidence"] = max(grouped[desc]["confidence"], conf)
            if cats:
                merged = set(grouped[desc].get("categories", [])) | {c for c in cats if c}
                grouped[desc]["categories"] = sorted(merged)
            if start_time is not None and end_time is not None:
                grouped[desc]["segments"].append({"start": start_time, "end": end_time, "confidence": conf})
        transformed["labels"] = list(grouped.values())
        return transformed
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Invalid metadata file")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading metadata: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)