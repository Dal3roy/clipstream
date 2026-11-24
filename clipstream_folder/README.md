# Clipstream

A short-video sharing web app (TikTok-style) built on Microsoft Azure for COM769 Coursework 2.

## Features

**Core**
- Sign up / log in
- Upload a video
- Scrollable video feed
- Comments on each video

**Advanced features**
1. **Automatic transcription:** uploaded videos are transcribed with Azure AI Speech and captions are shown on playback.
2. **Automatic conversion:** uploads are converted to standard MP4 (H.264) at several resolutions with FFmpeg, run in an Azure Function.
3. **Comment sentiment analysis:** each comment is analysed with Azure AI Language. Users see a sentiment label per comment and a sentiment summary per video.

Scalability (autoscale rules, load testing and profiling) is covered in the evaluation section of the report, not counted as a feature.

## Architecture (planned)

| Part | Azure service |
|---|---|
| Frontend | Azure Static Web Apps |
| Backend API | Azure App Service (Python / FastAPI) |
| Metadata and comments | Azure Cosmos DB (NoSQL, free tier) |
| Video files | Azure Blob Storage (browser uploads via SAS URL) |
| Conversion and transcription | Azure Functions (blob trigger) |
| Sentiment | Azure AI Language |
| Captions | Azure AI Speech |
| CI/CD | GitHub Actions |

## Repository layout

```
clipstream/
├── frontend/     HTML, CSS and JavaScript (mock data first, then the live API)
├── backend/      FastAPI app, tests and requirements
├── .github/      GitHub Actions workflows (tests and deployment)
└── README.md
```

## Status

- [x] Repository scaffold
- [x] Frontend: login, feed, upload, comments, likes, captions and sentiment (mock data)
- [x] Backend: mock API (FastAPI, in-memory store, sentiment via word list, tests in `backend/tests`)
- [ ] Frontend connected to backend
- [ ] Cosmos DB and Blob Storage
- [ ] Deploy to Azure
- [ ] CI/CD and tests
- [ ] Advanced features 1–3
