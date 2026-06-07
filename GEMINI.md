# OpenShorts Technical Documentation

This project is an AI-powered UGC (User Generated Content) and Short Video Generator. It converts long-form horizontal videos (YouTube) into viral vertical clips (TikTok, Reels, Shorts) and generates SaaS marketing videos using AI actors.

## 🏗 Project Structure

```text
openshorts/
├── app.py                # FastAPI Backend (Job management, API endpoints)
├── main.py               # Core Video Processing (Clipping, Vertical conversion, Active Speaker Tracking)
├── bot.py                # Telegram Bot Integration (Subprocess-based job triggering)
├── saasshorts.py         # AI UGC Generator (Scraping, Scripting, Actor Overlay)
├── editor.py             # Video editing utilities
├── subtitles.py          # Subtitle generation logic
├── thumbnail.py          # AI Thumbnail studio logic
├── docker-compose.yml    # Orchestration for Backend, Frontend, Renderer, and Bot
├── Dockerfile            # Shared Python environment (PyTorch, OpenCV, FFmpeg)
├── dashboard/            # Frontend (Vite + React + Tailwind)
├── remotion/             # Video rendering engine (React-based video)
└── render-service/       # Node.js service for Remotion rendering
```

## 🚀 Key Features & Components

### 1. Video Processing Engine (`main.py`)
- **Active Speaker Tracking**: Uses MediaPipe Face Detection and YOLO for fallback.
- **High-Fidelity Rendering**:
  - Resolution: 1080x1920 (FHD Vertical)
  - Scaling: `cv2.INTER_LANCZOS4` (Sharp upscaling)
  - FFmpeg: `veryslow` preset, `CRF 16`, High Profile 4.2.
- **Fast Mode (`--test`)**: Skips scene analysis for rapid quality checks (30s clips).

### 2. Telegram Bot (`bot.py`)
- Runs as a standalone service in Docker.
- **Commands**:
  - `/start`: Onboarding.
  - `/test <url>`: Generates a 30s quality preview (Fast Mode).
  - `<url>`: Triggers full viral clip analysis and processing.
- **Infrastructure**: Async subprocess execution with chunked log reading and background task management.

### 3. Source Quality Logic
- Uses `yt-dlp` with optimized format selection: `bestvideo+bestaudio/best`.
- Bypasses codec restrictions to ensure 1080p/4K sources are preferred.

## 🛠 Tech Stack
- **Backend**: Python 3.11, FastAPI, Uvicorn.
- **AI/ML**: Google Gemini (LLM), Faster-Whisper (Transcription), YOLOv8 (Tracking), MediaPipe (Face Detection).
- **Video**: OpenCV, FFmpeg.
- **Infrastructure**: Docker & Docker Compose.

## 📝 Configuration (Environment Variables)
Required in `.env`:
- `GEMINI_API_KEY`: For clip analysis and UGC scripting.
- `TELEGRAM_BOT_TOKEN`: For bot interaction.
- `YOUTUBE_COOKIES`: (Optional) Netscape format string for bypassing YouTube bot detection.

## ⚠️ Maintenance Notes
- **Docker Build**: Reuses `openshorts-app` image for both `backend` and `telegram-bot` to save resources.
- **Logs**: Monitor via `docker logs -f openshorts-telegram-bot`.
- **Temp Files**: Cleanup is handled per-job in the `output/` directory.
