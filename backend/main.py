from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
import json
from typing import List, Dict, Any
from pathlib import Path

app = FastAPI(title="RainLabel Video Analysis API", version="1.0.0")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # React dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
VIDEOS_DIR = Path("../videos")
METADATA_DIR = Path("../metadata")

# Ensure directories exist
VIDEOS_DIR.mkdir(exist_ok=True)
METADATA_DIR.mkdir(exist_ok=True)

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
    
    for video_file in VIDEOS_DIR.iterdir():
        if video_file.is_file() and video_file.suffix.lower() in video_extensions:
            video_info = {
                "name": video_file.stem,
                "filename": video_file.name,
                "path": f"/static/videos/{video_file.name}",
                "size": video_file.stat().st_size,
                "has_metadata": (METADATA_DIR / f"{video_file.stem}.json").exists()
            }
            videos.append(video_info)
    
    return videos

@app.get("/video/{video_name}")
async def get_video(video_name: str) -> Dict[str, Any]:
    """Get specific video information"""
    video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.webm']
    
    for ext in video_extensions:
        video_path = VIDEOS_DIR / f"{video_name}{ext}"
        if video_path.exists():
            return {
                "name": video_name,
                "filename": video_path.name,
                "path": f"/static/videos/{video_path.name}",
                "size": video_path.stat().st_size,
                "has_metadata": (METADATA_DIR / f"{video_name}.json").exists()
            }
    
    raise HTTPException(status_code=404, detail="Video not found")

@app.get("/metadata/{video_name}")
async def get_metadata(video_name: str) -> Dict[str, Any]:
    """Get video analysis metadata"""
    metadata_path = METADATA_DIR / f"{video_name}.json"
    
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
            metadata = json.load(f)
        return metadata
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Invalid metadata file")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading metadata: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)