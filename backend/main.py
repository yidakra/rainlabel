from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import json
from typing import List, Dict, Any
from pathlib import Path

app = FastAPI(title="RainLabel Video Analysis API", version="1.0.0")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],  # React dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Resolve project root regardless of current working directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Mount static files
VIDEOS_DIR = BASE_DIR / "videos"
METADATA_DIR = BASE_DIR / "metadata"
LABELS_DIR = BASE_DIR / "labels"

# Ensure directories exist
VIDEOS_DIR.mkdir(exist_ok=True)
METADATA_DIR.mkdir(exist_ok=True)
LABELS_DIR.mkdir(exist_ok=True)

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
    
    video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.webm']
    
    def has_metadata_for(stem: str) -> bool:
        # 1) metadata directory
        if (METADATA_DIR / f"{stem}.json").exists():
            return True
        # 2) sidecar next to any matching video file
        for ext in video_extensions:
            p = VIDEOS_DIR / f"{stem}{ext}"
            if p.exists():
                if Path(str(p) + ".json").exists():
                    return True
        # 3) labels directory (exact or prefix match)
        if (LABELS_DIR / f"{stem}.json").exists():
            return True
        try:
            for _ in LABELS_DIR.glob(f"{stem}*.json"):
                return True
        except Exception:
            pass
        return False

    for video_file in VIDEOS_DIR.iterdir():
        if video_file.is_file() and video_file.suffix.lower() in video_extensions:
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
    video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.webm']
    
    def has_metadata_for(stem: str) -> bool:
        if (METADATA_DIR / f"{stem}.json").exists():
            return True
        for ext in video_extensions:
            p = VIDEOS_DIR / f"{stem}{ext}"
            if p.exists() and Path(str(p) + ".json").exists():
                return True
        if (LABELS_DIR / f"{stem}.json").exists():
            return True
        try:
            for _ in LABELS_DIR.glob(f"{stem}*.json"):
                return True
        except Exception:
            pass
        return False

    for ext in video_extensions:
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
    metadata_path = METADATA_DIR / f"{video_name}.json"
    # Fallback: check for sidecar JSON next to any matching video file
    if not metadata_path.exists():
        video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.webm']
        for ext in video_extensions:
            candidate = VIDEOS_DIR / f"{video_name}{ext}"
            if candidate.exists():
                sidecar = Path(str(candidate) + ".json")
                if sidecar.exists():
                    metadata_path = sidecar
                    break
    # Fallback: check labels directory (supports both <name>.json and <name>* .json)
    if not metadata_path.exists():
        candidate = LABELS_DIR / f"{video_name}.json"
        if candidate.exists():
            metadata_path = candidate
        else:
            try:
                for p in LABELS_DIR.glob(f"{video_name}*.json"):
                    metadata_path = p
                    break
            except Exception:
                pass
    
    if not metadata_path.exists():
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