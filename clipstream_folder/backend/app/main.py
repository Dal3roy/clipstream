"""Clipstream API.

Two modes, chosen by the settings in backend/.env:
- Azure mode (COSMOS_URI and COSMOS_KEY set): data lives in Cosmos DB, and uploads go
  straight to Blob Storage using a short-lived link.
- Local mode (no Azure settings): in-memory data and a mock upload endpoint.

Run locally from the backend folder:
    uvicorn app.main:app --reload --port 8001
"""
from __future__ import annotations

import threading

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware

from .blob import upload_blob_name
from .blob import upload_url as sas_upload_url
from .config import Settings, load_settings
from .cosmos_store import CosmosStore
from .schemas import CommentIn, LoginIn, MAX_UPLOAD_BYTES, SignupIn, UploadIn
from .store import SEED_PATH, Store

# Local mode only: how long the fake "processing" takes. Azure Functions replace this in step 5.
PROCESSING_SECONDS = 4
MOCK_TRANSCRIPT = ["Mock transcript: real captions come from Azure AI Speech in step 5."]

# The frontend's dev server. Add your Azure Static Web Apps address here when you deploy.
ALLOWED_ORIGINS = ["http://localhost:8000", "http://127.0.0.1:8000"]


def build_store(settings: Settings):
    if settings.use_cosmos:
        return CosmosStore(settings.cosmos_uri, settings.cosmos_key, settings.cosmos_database)
    return Store.from_seed_file(SEED_PATH)


def _bearer_token(authorization: str | None) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()
    return None


def create_app(store=None, settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    store = store or build_store(settings)

    app = FastAPI(title="Clipstream API", version="0.5.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def current_user(authorization: str | None = Header(default=None)) -> dict:
        token = _bearer_token(authorization)
        if token is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Log in to continue.")
        user = store.user_for_token(token)
        if user is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Your session has expired. Log in again.")
        return user

    def require_video(video_id: str) -> dict:
        video = store.get_video(video_id)
        if video is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Video not found")
        return video

    # ---------- auth ----------

    @app.post("/api/auth/signup", status_code=201)
    def signup(body: SignupIn):
        try:
            return store.signup(body.name, body.email, body.password)
        except ValueError as exc:
            raise HTTPException(status.HTTP_409_CONFLICT, str(exc))

    @app.post("/api/auth/login")
    def login(body: LoginIn):
        user = store.login(body.email, body.password)
        if user is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password.")
        return user

    @app.post("/api/auth/logout", status_code=204)
    def logout(authorization: str | None = Header(default=None)):
        token = _bearer_token(authorization)
        if token:
            store.logout(token)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    # ---------- videos ----------

    @app.get("/api/videos")
    def list_videos():
        return store.list_videos()

    @app.get("/api/videos/{video_id}")
    def get_video(video_id: str):
        return require_video(video_id)

    @app.post("/api/videos/upload-url", status_code=201)
    def create_upload(body: UploadIn, request: Request, user: dict = Depends(current_user)):
        video = store.create_video(user, body.title, body.caption)
        if settings.use_blob:
            # Azure mode: the browser uploads straight to Blob Storage with this link.
            blob_name = upload_blob_name(video["id"], body.fileName)
            upload_url = sas_upload_url(
                settings.storage_account, settings.storage_key, settings.raw_container, blob_name
            )
        else:
            # Local mode: the browser uploads to this API, which discards the file.
            upload_url = f"{str(request.base_url).rstrip('/')}/api/mock-blob/{video['id']}"
        return {"videoId": video["id"], "uploadUrl": upload_url}

    @app.put("/api/mock-blob/{video_id}", status_code=201)
    async def mock_blob(video_id: str, request: Request):
        require_video(video_id)
        size = 0
        async for chunk in request.stream():
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "File is larger than 500 MB.")
        timer = threading.Timer(PROCESSING_SECONDS, store.mark_ready, args=(video_id, MOCK_TRANSCRIPT))
        timer.daemon = True
        timer.start()
        return {"received": size}

    # ---------- comments ----------

    @app.get("/api/videos/{video_id}/comments")
    def list_comments(video_id: str):
        require_video(video_id)
        return store.list_comments(video_id)

    @app.post("/api/videos/{video_id}/comments", status_code=201)
    def add_comment(video_id: str, body: CommentIn, user: dict = Depends(current_user)):
        require_video(video_id)
        text = body.text.strip()
        if not text:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Comment cannot be empty.")
        return store.add_comment(video_id, user, text)

    # ---------- likes ----------

    @app.post("/api/videos/{video_id}/like")
    def like_video(video_id: str, user: dict = Depends(current_user)):
        result = store.like(video_id, user["username"])
        if result is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Video not found")
        liked, count = result
        return {"liked": liked, "likeCount": count}

    @app.delete("/api/videos/{video_id}/like")
    def unlike_video(video_id: str, user: dict = Depends(current_user)):
        result = store.unlike(video_id, user["username"])
        if result is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Video not found")
        liked, count = result
        return {"liked": liked, "likeCount": count}

    return app


app = create_app()
