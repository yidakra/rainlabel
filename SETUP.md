# RainLabel Development Setup

## Quick Start

1. **Install dependencies:**
   ```bash
   # Backend
   cd backend
   pip install -r requirements.txt
   
   # Frontend
   cd frontend
   npm install
   ```

2. **Run the application:**
   ```bash
   # Terminal 1 - Backend
   cd backend && python main.py
   
   # Terminal 2 - Frontend
   cd frontend && npm start
   ```

3. **Access the application:**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000

## Adding Videos

1. Place video files (.mp4, .avi, .mov, .mkv, .webm) in the `videos/` directory
2. Run video analysis (optional):
   ```bash
   python scripts/analyze_video.py your_video.mp4
   ```
3. Metadata will be saved next to the video as a sidecar JSON: `videos/your_video.mp4.json`

## API Documentation

Visit http://localhost:8000/docs for interactive API documentation.

## Project Structure

- `backend/` - FastAPI server with video and metadata endpoints
- `frontend/` - React application with video player and analysis UI
- `videos/` - Video file storage and sidecar JSON metadata
- `scripts/analyze_video.py` - Google Cloud Video Intelligence integration script