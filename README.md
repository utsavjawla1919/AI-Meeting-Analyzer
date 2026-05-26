# 🎙️ AI Meeting Analyzer

> **Upload meeting recordings. Get AI-powered transcripts, summaries, action items, sentiment analysis, and a full analytics dashboard — automatically.**

[![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.0-black?logo=flask)](https://flask.palletsprojects.com)
[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react)](https://react.dev)
[![MongoDB](https://img.shields.io/badge/MongoDB-7.0-green?logo=mongodb)](https://mongodb.com)
[![Whisper](https://img.shields.io/badge/OpenAI-Whisper-412991?logo=openai)](https://github.com/openai/whisper)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker)](https://docker.com)

---

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Quick Start — Local Development](#quick-start--local-development)
- [Docker Deployment](#docker-deployment)
- [Production Deployment](#production-deployment)
- [Environment Variables](#environment-variables)
- [API Reference](#api-reference)
- [AI Pipeline](#ai-pipeline)
- [Database Schema](#database-schema)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

AI Meeting Analyzer is a full-stack application that transforms raw meeting recordings into structured, actionable intelligence. Upload an audio or video file and the system automatically:

1. **Transcribes** speech to text using OpenAI Whisper with speaker diarization
2. **Analyzes** the transcript with spaCy, NLTK, and scikit-learn
3. **Summarizes** the meeting using HuggingFace BART/T5
4. **Extracts** action items, decisions, and key discussion points
5. **Scores** sentiment per speaker and over time using DistilBERT
6. **Presents** everything in a modern React dashboard with Chart.js visualizations

---

## Features

### 🔐 Authentication
- JWT-based register/login with bcrypt password hashing
- Access token (1h) + refresh token (30d) with silent auto-refresh
- Role-based access control (`user` / `admin`)
- Token revocation via MongoDB TTL-indexed blocklist

### 📤 Meeting Upload
- Drag-and-drop file uploader supporting **MP3, MP4, WAV, M4A, WEBM, OGG, FLAC, AVI, MKV**
- Chunked multipart upload with real-time progress bar
- File validation (format, size up to 500 MB, duration up to 2 hours)
- Background AI processing with per-stage status polling

### 🎙️ Speech-to-Text (Whisper)
- OpenAI Whisper (tiny → large model) with automatic model selection
- ffmpeg audio extraction from video files
- Auto-chunking of recordings > 10 minutes with timestamp stitching
- Language auto-detection with confidence score
- Speaker diarization via pyannote-audio (optional, requires HuggingFace token)
- Low-confidence segment filtering to reduce hallucinations

### 🧠 AI Analysis
- **Summarization**: HuggingFace BART-large-CNN with multi-chunk support
- **Action items**: 6-pattern regex extraction with assignee, due date, and priority
- **Decisions**: 7-pattern detection (agreed, decided, approved, consensus…)
- **Key points**: TF-IDF sentence ranking with keyword density scoring
- **AI title**: Auto-generated descriptive meeting title
- **Recommendations**: 5 smart follow-up suggestions

### 📊 NLP Processing
- **Keywords**: scikit-learn TF-IDF with bigrams, top 25 ranked by score
- **Named entities**: spaCy NER (PERSON, ORG, DATE, GPE, PRODUCT, EVENT)
- **Topic detection**: 10 seed categories scored by keyword hit density
- **Word cloud**: POS-tagged, size-weighted (NOUN/VERB/ADJ colored)
- **Co-occurrence graph**: Force-graph node/edge data for D3

### 😊 Sentiment Analysis
- DistilBERT SST-2 with batch processing (16 segments/batch)
- Neutral zone: confidence < 0.65 mapped to neutral (fixes SST-2 binary limitation)
- NLTK VADER fallback when transformer unavailable
- Per-segment, per-speaker, and overall aggregation
- Smoothed timeline data (sliding window, size 5) for Chart.js
- Meeting health score (0–100) with 4-factor breakdown

### 📈 Dashboard
- Stat cards: total meetings, hours analyzed, completed, failed
- Weekly bar chart (last 8 weeks)
- Status distribution doughnut chart
- Searchable, filterable, paginated meeting list
- Dark / light mode with system preference detection

### 📄 Meeting Detail
- 4-tab view: **Summary** / **Transcript** / **Sentiment** / **Actions**
- Timestamped, speaker-colored transcript segments
- Sentiment timeline line chart (smoothed positive/negative)
- Per-speaker stacked sentiment bar chart
- One-click PDF export (full report or transcript only)

### 🔍 Search
- Full-text search across transcripts and summaries
- 400ms debounced with match-type labels and highlighted snippets

### 👤 Admin Panel
- Platform stats overview
- Paginated user table with activate/deactivate and role promotion
- Admin hard-delete of any meeting

### 📁 Export
- **Full report PDF**: cover, metadata, summary, action items table, decisions, sentiment, keywords, full transcript
- **Transcript PDF**: speaker-labeled, timestamped segments only
- ReportLab with custom brand styling

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  CLIENT  (React 18 + Tailwind CSS + Chart.js)                    │
│  Login · Dashboard · Upload · Meeting Detail · Search · Admin    │
└───────────────────────┬──────────────────────────────────────────┘
                        │  REST API + JWT (Bearer token)
┌───────────────────────▼──────────────────────────────────────────┐
│  API GATEWAY  (Python Flask 3 + Gunicorn)                        │
│  /api/auth  /api/meetings  /api/analysis  /api/users  /api/export│
│  JWT Middleware · Role Guards · File Validation · Rate Limiting  │
└───────────┬──────────────────────────────┬───────────────────────┘
            │ background thread            │ sync queries
┌───────────▼──────────────────┐  ┌───────▼───────────────────────┐
│  AI PIPELINE                 │  │  MongoDB 7                    │
│  Stage 1: Whisper STT        │  │  users · meetings             │
│  Stage 2: spaCy + NLTK NLP   │  │  transcripts · analyses       │
│  Stage 3: BART Summarization │  │  token_blocklist              │
│  Stage 4: DistilBERT Sentiment│  │  13 indexes + TTL             │
└──────────────────────────────┘  └───────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | React 18, React Router 6, Tailwind CSS 3, Chart.js 4, Axios, react-dropzone |
| **Backend** | Python 3.11, Flask 3, Flask-JWT-Extended, Flask-CORS, Gunicorn |
| **Database** | MongoDB 7 (PyMongo — no ODM) |
| **Auth** | JWT (HS256), bcrypt, TTL token blocklist |
| **STT** | OpenAI Whisper, ffmpeg, pyannote-audio (optional) |
| **NLP** | spaCy en_core_web_sm, NLTK, scikit-learn TF-IDF |
| **AI** | HuggingFace Transformers (BART-large-CNN, DistilBERT SST-2) |
| **PDF** | ReportLab |
| **Cloud Storage** | Local filesystem (default) or AWS S3 |
| **Container** | Docker, Docker Compose, Nginx |

---

## Project Structure

```
ai-meeting-analyzer/
├── docker-compose.yml              # Full stack orchestration
├── nginx/
│   └── nginx.conf                  # Reverse proxy config
│
├── backend/
│   ├── app.py                      # Flask application factory
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── .env.example
│   │
│   ├── config/
│   │   └── settings.py             # Environment-based config
│   │
│   ├── models/
│   │   ├── models.py               # UserModel, MeetingModel, TranscriptModel, AnalysisModel
│   │   └── token_blocklist.py      # JWT revocation with TTL index
│   │
│   ├── middleware/
│   │   ├── auth_middleware.py      # jwt_required_custom, admin_required
│   │   └── validation.py           # Input validators, paginate_params
│   │
│   ├── routes/
│   │   ├── auth_routes.py
│   │   ├── meeting_routes.py
│   │   ├── analysis_routes.py
│   │   ├── user_routes.py
│   │   └── export_routes.py
│   │
│   ├── controllers/
│   │   ├── auth_controller.py      # register, login, refresh, logout
│   │   ├── meeting_controller.py   # upload, list, get, status, delete
│   │   ├── analysis_controller.py  # get analysis, sentiment, actions, search
│   │   ├── user_controller.py      # profile, preferences, admin ops
│   │   └── export_controller.py    # PDF generation (full + transcript)
│   │
│   ├── services/
│   │   ├── pipeline_service.py     # Master orchestrator (4 stages)
│   │   ├── stt_service.py          # Whisper STT + diarization
│   │   ├── nlp_service.py          # TF-IDF, spaCy NER, topics
│   │   ├── summarization_service.py# BART, action/decision extraction
│   │   ├── sentiment_service.py    # DistilBERT + VADER + timeline
│   │   ├── speaker_service.py      # Talk-time, pace, interruptions
│   │   └── keyword_service.py      # Word cloud, co-occurrence, topic flow
│   │
│   ├── ai_pipeline/
│   │   ├── __init__.py             # Thread-safe model registry
│   │   ├── audio_utils.py          # ffmpeg extraction, chunking, silence detection
│   │   └── progress.py             # PipelineProgress context manager
│   │
│   ├── utils/
│   │   ├── file_utils.py           # save/delete files, S3 support
│   │   └── serializer.py           # MongoDB → JSON serialization
│   │
│   └── scripts/
│       ├── db_setup.py             # Index initialization script
│       └── mongo-init.js           # Docker MongoDB seed script
│
└── frontend/
    ├── package.json
    ├── tailwind.config.js
    ├── Dockerfile
    ├── nginx.conf
    ├── public/index.html
    └── src/
        ├── App.jsx                 # Router + Protected/Public guards
        ├── index.css               # Design system, animations, glass UI
        ├── index.js
        │
        ├── context/
        │   ├── AuthContext.jsx     # Global auth state + token management
        │   └── ThemeContext.jsx    # Dark/light mode
        │
        ├── hooks/
        │   └── useMeetings.js      # useMeetings, useMeeting, usePollStatus, useSearch
        │
        ├── services/
        │   └── api.js              # Axios + interceptors + all API functions
        │
        ├── components/
        │   ├── layout/
        │   │   └── AppLayout.jsx   # Collapsible sidebar + mobile nav
        │   └── charts/
        │       ├── SentimentDoughnutChart.jsx
        │       ├── SentimentTimelineChart.jsx
        │       ├── WeeklyBarChart.jsx
        │       └── SpeakerBarChart.jsx
        │
        └── pages/
            ├── LoginPage.jsx       # Split-panel auth UI
            ├── RegisterPage.jsx    # Password strength meter
            ├── DashboardPage.jsx   # Stats + chart + meeting list
            ├── UploadPage.jsx      # Dropzone + pipeline progress
            ├── MeetingPage.jsx     # 4-tab detail view + export
            ├── SearchPage.jsx      # Debounced full-text search
            ├── ProfilePage.jsx     # Profile + password + preferences
            └── AdminPage.jsx       # Platform stats + user management
```

---

## Prerequisites

### System requirements
- **OS**: Linux, macOS, or Windows (WSL2)
- **Python**: 3.11+
- **Node.js**: 18+
- **MongoDB**: 7.0+ (local or Atlas)
- **ffmpeg**: Required for audio/video processing

### Install ffmpeg

```bash
# Ubuntu / Debian
sudo apt update && sudo apt install -y ffmpeg

# macOS
brew install ffmpeg

# Windows (winget)
winget install ffmpeg
```

### Optional: GPU acceleration
For significantly faster Whisper transcription and HuggingFace inference:
```bash
# Install CUDA-enabled PyTorch (adjust version for your CUDA)
pip install torch==2.3.1+cu118 --index-url https://download.pytorch.org/whl/cu118
# Then in stt_service.py change: fp16=True, device=0
# In sentiment/summarization services change: device=0
```

---

## Quick Start — Local Development

### 1. Clone the repository

```bash
git clone https://github.com/your-org/ai-meeting-analyzer.git
cd ai-meeting-analyzer
```

### 2. Backend setup

```bash
cd backend

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate

# Install dependencies (takes ~5 min — downloads ML models)
pip install -r requirements.txt

# Download spaCy English model
python -m spacy download en_core_web_sm

# Download NLTK data
python -c "
import nltk
nltk.download('punkt_tab')
nltk.download('stopwords')
nltk.download('averaged_perceptron_tagger')
nltk.download('vader_lexicon')
"

# Configure environment
cp .env.example .env
# Edit .env with your settings (see Environment Variables section)

# Initialize database indexes + seed users
python scripts/db_setup.py

# Start Flask development server
python app.py
# → Backend running at http://localhost:5000
# → API health: http://localhost:5000/api/health
```

### 3. Frontend setup

```bash
cd frontend

# Install dependencies
npm install

# Start React development server
npm start
# → Frontend running at http://localhost:3000
```

### 4. Access the app

| URL | Description |
|-----|-------------|
| `http://localhost:3000` | React frontend |
| `http://localhost:5000/api/health` | Backend health check |
| `http://localhost:27017` | MongoDB (if running locally) |

**Default credentials** (created by `db_setup.py`):
| Role | Email | Password |
|------|-------|----------|
| Admin | `admin@meetinganalyzer.app` | `Admin@1234` |
| Demo  | `demo@meetinganalyzer.app`  | `Admin@1234` |

> ⚠️ **Change these passwords immediately in production.**

---

## Docker Deployment

The easiest way to run the complete stack.

### 1. Configure environment

```bash
# Copy and edit backend environment
cp backend/.env.example backend/.env
```

Minimum required changes in `backend/.env`:
```env
SECRET_KEY=your-super-secret-flask-key-here
JWT_SECRET_KEY=your-super-secret-jwt-key-here
MONGO_URI=mongodb://admin:secret@mongodb:27017
```

### 2. Build and start

```bash
# Build all images and start containers
docker-compose up --build

# Or run in background
docker-compose up --build -d
```

### 3. Verify services

```bash
# Check all containers are healthy
docker-compose ps

# View backend logs
docker-compose logs -f backend

# View pipeline processing logs
docker-compose logs -f backend | grep Pipeline
```

### 4. Access the app

- Frontend: `http://localhost` (port 80 via Nginx)
- Backend API: `http://localhost/api`
- Direct backend: `http://localhost:5000`

### 5. Stop and clean up

```bash
# Stop containers
docker-compose down

# Stop and remove volumes (deletes all data)
docker-compose down -v
```

---

## Production Deployment

### Cloud VM (Ubuntu 22.04)

#### System setup

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install -y docker.io docker-compose-v2 nginx certbot python3-certbot-nginx

# Add user to docker group
sudo usermod -aG docker $USER && newgrp docker
```

#### Deploy

```bash
# Clone repo
git clone https://github.com/your-org/ai-meeting-analyzer.git
cd ai-meeting-analyzer

# Configure environment
cp backend/.env.example backend/.env
nano backend/.env   # Fill in production values

# Create .env for docker-compose secrets
cat > .env << EOF
MONGO_USER=admin
MONGO_PASSWORD=$(openssl rand -hex 24)
EOF

# Build and start
docker-compose -f docker-compose.yml up --build -d
```

#### SSL with Let's Encrypt

```bash
# Point your domain DNS to the server IP, then:
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com

# Test auto-renewal
sudo certbot renew --dry-run
```

#### Update nginx.conf for HTTPS

```nginx
server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    ssl_certificate     /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    # ... rest of config
}

server {
    listen 80;
    return 301 https://$host$request_uri;
}
```

### AWS / GCP / Azure

#### Recommended instance types

| Provider | Instance | vCPU | RAM | Notes |
|----------|----------|------|-----|-------|
| AWS | `t3.xlarge` | 4 | 16 GB | Good for Whisper base model |
| AWS | `g4dn.xlarge` | 4 | 16 GB + T4 GPU | For GPU inference |
| GCP | `n2-standard-4` | 4 | 16 GB | |
| Azure | `Standard_D4s_v3` | 4 | 16 GB | |

> Minimum: 4 vCPU, 8 GB RAM for Whisper `base` + BART on CPU.
> Recommended: 8 vCPU, 16 GB RAM for `small` model + concurrent users.

#### AWS S3 file storage

Update `backend/.env`:
```env
USE_S3=true
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_BUCKET_NAME=your-meeting-files-bucket
AWS_REGION=us-east-1
```

Create an S3 bucket with server-side encryption and block public access.

#### MongoDB Atlas

```env
MONGO_URI=mongodb+srv://username:password@cluster.xxxxx.mongodb.net/?retryWrites=true&w=majority
MONGO_DB_NAME=ai_meeting_analyzer
```

---

## Environment Variables

### Backend (`backend/.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `FLASK_ENV` | `development` | `development` or `production` |
| `SECRET_KEY` | — | **Required.** Flask secret key (min 32 chars) |
| `JWT_SECRET_KEY` | — | **Required.** JWT signing key (min 32 chars) |
| `JWT_ACCESS_HOURS` | `1` | Access token lifetime in hours |
| `JWT_REFRESH_DAYS` | `30` | Refresh token lifetime in days |
| `MONGO_URI` | `mongodb://localhost:27017` | MongoDB connection string |
| `MONGO_DB_NAME` | `ai_meeting_analyzer` | Database name |
| `UPLOAD_FOLDER` | `uploads` | Local file storage directory |
| `MAX_UPLOAD_MB` | `500` | Maximum upload file size in MB |
| `CORS_ORIGINS` | `http://localhost:3000` | Comma-separated allowed origins |
| `WHISPER_MODEL` | `base` | `tiny`, `base`, `small`, `medium`, `large` |
| `SUMMARIZER_MODEL` | `facebook/bart-large-cnn` | HuggingFace model ID |
| `SENTIMENT_MODEL` | `distilbert-base-uncased-finetuned-sst-2-english` | Sentiment model |
| `HUGGINGFACE_TOKEN` | — | Required for pyannote speaker diarization |
| `USE_S3` | `false` | Enable AWS S3 storage |
| `AWS_ACCESS_KEY_ID` | — | AWS credentials (if `USE_S3=true`) |
| `AWS_SECRET_ACCESS_KEY` | — | AWS credentials (if `USE_S3=true`) |
| `AWS_BUCKET_NAME` | — | S3 bucket name |
| `AWS_REGION` | `us-east-1` | AWS region |
| `DEFAULT_PAGE_SIZE` | `10` | Default API pagination size |
| `MAX_PAGE_SIZE` | `50` | Maximum API pagination size |

### Model size guide

| Whisper Model | VRAM / RAM | Speed (CPU) | Accuracy |
|---------------|------------|-------------|----------|
| `tiny` | ~1 GB | Very fast | Basic |
| `base` | ~1 GB | Fast | Good |
| `small` | ~2 GB | Moderate | Better |
| `medium` | ~5 GB | Slow | Great |
| `large` | ~10 GB | Very slow | Best |

---

## API Reference

### Authentication

| Method | Endpoint | Auth | Body | Response |
|--------|----------|------|------|----------|
| POST | `/api/auth/register` | None | `{email, password, full_name}` | `{user, access_token, refresh_token}` |
| POST | `/api/auth/login` | None | `{email, password}` | `{user, access_token, refresh_token}` |
| POST | `/api/auth/refresh` | Refresh token | — | `{access_token}` |
| GET | `/api/auth/me` | JWT | — | `{user}` |
| POST | `/api/auth/logout` | JWT | — | `{message}` |
| PUT | `/api/auth/password` | JWT | `{current_password, new_password}` | `{message}` |

### Meetings

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/meetings/upload` | JWT | Upload file (multipart/form-data) |
| GET | `/api/meetings/` | JWT | List meetings `?page=1&limit=10&search=&status=` |
| GET | `/api/meetings/stats` | JWT | Dashboard aggregate stats |
| GET | `/api/meetings/:id` | JWT | Full meeting + transcript + analysis |
| GET | `/api/meetings/:id/status` | JWT | Poll pipeline progress |
| PUT | `/api/meetings/:id` | JWT | Update title / tags |
| DELETE | `/api/meetings/:id` | JWT | Soft delete |

### Analysis

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/analysis/search?q=` | JWT | Full-text search |
| GET | `/api/analysis/:id` | JWT | Full analysis document |
| GET | `/api/analysis/:id/transcript` | JWT | Transcript with speaker segments |
| GET | `/api/analysis/:id/sentiment` | JWT | Sentiment (overall + speaker + timeline) |
| GET | `/api/analysis/:id/actions` | JWT | Action items + decisions + key points |
| GET | `/api/analysis/:id/keywords` | JWT | Keywords + topics + entities |
| POST | `/api/analysis/:id/retry` | JWT | Re-trigger failed pipeline |

### Export

| Method | Endpoint | Auth | Response |
|--------|----------|------|----------|
| GET | `/api/export/:id/pdf` | JWT | Full report PDF (blob) |
| GET | `/api/export/:id/transcript` | JWT | Transcript-only PDF (blob) |

### Users

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/users/profile` | JWT | Get own profile |
| PUT | `/api/users/profile` | JWT | Update name / avatar |
| PUT | `/api/users/preferences` | JWT | Dark mode, notifications |
| DELETE | `/api/users/account` | JWT | Deactivate account |
| GET | `/api/users/admin/stats` | Admin | Platform stats |
| GET | `/api/users/admin/users` | Admin | List all users |
| PUT | `/api/users/admin/users/:id/toggle` | Admin | Activate / deactivate |
| PUT | `/api/users/admin/users/:id/role` | Admin | Change role |
| DELETE | `/api/users/admin/meetings/:id` | Admin | Hard delete meeting |

---

## AI Pipeline

The pipeline runs as a background thread immediately after upload and progresses through 4 stages. Each stage updates `meetings.processing_stages` in MongoDB so the frontend can poll for live progress.

```
Upload complete
      │
      ▼
┌─────────────────┐
│ Stage 1: STT    │  Whisper transcribes audio → timestamped segments
│                 │  + pyannote diarization → speaker labels
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Stage 2: NLP    │  spaCy NER · NLTK tokenization · TF-IDF keywords
│                 │  Topic clustering · Key sentence ranking
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Stage 3: Sum.   │  BART summarization (chunked for long meetings)
│                 │  Action items · Decisions · AI title · Recommendations
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Stage 4: Sent.  │  DistilBERT batch scoring · VADER fallback
│                 │  Per-speaker aggregation · Timeline smoothing
└────────┬────────┘
         │
         ▼
   status: "completed"
```

### Stage timing (approximate, CPU, 30-min meeting)

| Stage | Whisper base | Whisper small |
|-------|-------------|---------------|
| STT | 3–8 min | 8–20 min |
| NLP | 5–15 sec | 5–15 sec |
| Summarization | 30–90 sec | 30–90 sec |
| Sentiment | 20–60 sec | 20–60 sec |

> GPU reduces STT time by **10–20×** and inference by **5–10×**.

---

## Database Schema

### `users`
```json
{
  "_id": "ObjectId",
  "email": "string (unique)",
  "password": "BinData (bcrypt)",
  "full_name": "string",
  "role": "user | admin",
  "preferences": { "dark_mode": bool, "email_notify": bool, "default_language": "en" },
  "is_active": true,
  "last_login": "ISODate | null",
  "created_at": "ISODate",
  "updated_at": "ISODate"
}
```

### `meetings`
```json
{
  "_id": "ObjectId",
  "user_id": "ObjectId (ref: users)",
  "title": "string",
  "ai_title": "string | null",
  "file_path": "string (local path or S3 key)",
  "file_name": "string",
  "file_size": "number (bytes)",
  "file_type": "string (MIME)",
  "duration_seconds": "number",
  "language": "string (ISO 639-1) | null",
  "status": "pending | transcribing | analyzing | completed | failed",
  "processing_stages": {
    "upload": "pending | running | completed | failed",
    "transcription": "...",
    "nlp": "...",
    "summarization": "...",
    "sentiment": "..."
  },
  "participants": ["string"],
  "tags": ["string"],
  "is_deleted": false,
  "created_at": "ISODate",
  "updated_at": "ISODate"
}
```

### `transcripts`
```json
{
  "_id": "ObjectId",
  "meeting_id": "ObjectId (ref: meetings, unique)",
  "full_text": "string",
  "segments": [
    { "speaker": "Speaker 1", "start": 0.0, "end": 4.2, "text": "Hello everyone." }
  ],
  "language": "en",
  "word_count": 1842,
  "created_at": "ISODate"
}
```

### `analyses`
```json
{
  "_id": "ObjectId",
  "meeting_id": "ObjectId (ref: meetings, unique)",
  "summary": "string | null",
  "ai_title": "string | null",
  "action_items": [{ "text": "string", "assignee": "string|null", "due_date": "string|null", "priority": "high|medium|low" }],
  "decisions": [{ "text": "string", "context": "string|null" }],
  "key_points": ["string"],
  "keywords": [{ "word": "string", "score": 0.94, "frequency": 12 }],
  "topics": [{ "label": "string", "confidence": 0.85, "keywords": ["string"] }],
  "entities": [{ "text": "string", "label": "PERSON", "type": "Person" }],
  "sentiment_overall": { "label": "positive", "score": 0.82, "positive": 0.6, "negative": 0.1, "neutral": 0.3 },
  "sentiment_by_speaker": { "Speaker 1": { "label": "positive", "score": 0.78, "..." } },
  "sentiment_timeline": [{ "segment_index": 0, "start": 0.0, "label": "neutral", "score": 0.51, "smoothed_positive": 0.35 }],
  "recommendations": ["string"],
  "meeting_score": 72,
  "pipeline_timings": { "transcription": 184.2, "nlp": 8.1, "summarization": 45.3, "sentiment": 22.7 },
  "created_at": "ISODate",
  "updated_at": "ISODate"
}
```

### `token_blocklist`
```json
{
  "_id": "ObjectId",
  "jti": "string (unique)",
  "user_id": "ObjectId",
  "expires_at": "ISODate (TTL index — auto-purged)",
  "created_at": "ISODate"
}
```

---

## Troubleshooting

### Backend won't start
```bash
# Check MongoDB is running
mongosh --eval "db.adminCommand('ping')"

# Verify environment
python -c "from config.settings import Config; print(Config.MONGO_URI)"

# Check port is free
lsof -i :5000
```

### Whisper model download fails
```bash
# Models cache in ~/.cache/whisper/ — pre-download manually
python -c "import whisper; whisper.load_model('base')"
```

### ffmpeg not found
```bash
# Verify installation
ffmpeg -version
ffprobe -version

# If using Docker and ffmpeg missing from image, rebuild:
docker-compose build --no-cache backend
```

### Pipeline stuck at "transcribing"
```bash
# Check backend logs for errors
docker-compose logs backend | grep -i "error\|failed\|pipeline"

# Retry via API
curl -X POST http://localhost:5000/api/analysis/<meeting_id>/retry \
  -H "Authorization: Bearer <token>"
```

### Out of memory (large Whisper model)
```env
# Use a smaller model in .env
WHISPER_MODEL=tiny
```

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Commit with conventional commits: `git commit -m "feat: add speaker diarization toggle"`
4. Push and open a Pull Request

### Code style
- **Python**: PEP 8, docstrings on all public functions, type hints encouraged
- **JavaScript/JSX**: Prettier defaults, functional components only, named exports
- **Git**: Conventional commits (`feat:`, `fix:`, `docs:`, `refactor:`)

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">

Built with ❤️ using OpenAI Whisper · HuggingFace · spaCy · React · Flask · MongoDB

**[Report Bug](https://github.com/your-org/ai-meeting-analyzer/issues) · [Request Feature](https://github.com/your-org/ai-meeting-analyzer/issues)**

</div>
