"""In-memory data store for the mock API.

Step 5 replaces this with Cosmos DB (videos, comments, likes, users) and Blob Storage.
Keep the method names and return shapes the same so the routes don't change.
Everything here is lost when the server restarts, which is fine for development.
"""
from __future__ import annotations

import hashlib
import json
import secrets
import threading
from datetime import datetime, timezone
from pathlib import Path

from .sentiment import analyse

SEED_PATH = Path(__file__).resolve().parents[2] / "frontend" / "data" / "videos.json"
AVATAR_COLOURS = ["#c2410c", "#be123c", "#047857", "#3b5bdb", "#0f766e", "#7c3aed"]

# A demo account so you can log in straight away. Not for real use.
DEMO_NAME = "Demo User"
DEMO_EMAIL = "demo@clipstream.test"
DEMO_PASSWORD = "password123"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _hash_password(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000).hex()


def _initials(name: str) -> str:
    parts = name.split()
    initials = "".join(part[0] for part in parts[:2]).upper()
    return initials or name[:2].upper()


def _public_user(user: dict) -> dict:
    return {
        "username": user["username"],
        "displayName": user["displayName"],
        "initials": user["initials"],
        "color": user["color"],
    }


class Store:
    def __init__(self, seed: dict):
        self._lock = threading.RLock()
        self._videos: list[dict] = [dict(v) for v in seed["videos"]]
        self._comments: list[dict] = []
        for comment in seed["comments"]:
            comment = dict(comment)
            comment["sentiment"] = analyse(comment["text"])
            self._comments.append(comment)
        self._likes: set[tuple[str, str]] = set()  # (videoId, username)
        self._users: dict[str, dict] = {}          # username -> user record
        self._tokens: dict[str, str] = {}          # session token -> username
        self._video_counter = 2000
        self._comment_counter = 100
        self._create_user(DEMO_NAME, DEMO_EMAIL, DEMO_PASSWORD)

    @classmethod
    def from_seed_file(cls, path: Path = SEED_PATH) -> "Store":
        return cls(json.loads(path.read_text(encoding="utf-8")))

    # ---------- users and sessions ----------

    def _create_user(self, name: str, email: str, password: str) -> dict:
        username = email.split("@")[0].lower()
        if username in self._users:
            raise ValueError("An account with that email already exists.")
        salt = secrets.token_bytes(16)
        user = {
            "username": username,
            "displayName": name,
            "initials": _initials(name),
            "color": AVATAR_COLOURS[len(self._users) % len(AVATAR_COLOURS)],
            "salt": salt,
            "passwordHash": _hash_password(password, salt),
        }
        self._users[username] = user
        return user

    def _new_session(self, user: dict) -> dict:
        token = secrets.token_urlsafe(24)
        self._tokens[token] = user["username"]
        return {**_public_user(user), "token": token}

    def signup(self, name: str, email: str, password: str) -> dict:
        with self._lock:
            user = self._create_user(name, email, password)
            return self._new_session(user)

    def login(self, email: str, password: str) -> dict | None:
        username = email.split("@")[0].lower()
        with self._lock:
            user = self._users.get(username)
            if user is None:
                return None
            if not secrets.compare_digest(_hash_password(password, user["salt"]), user["passwordHash"]):
                return None
            return self._new_session(user)

    def user_for_token(self, token: str) -> dict | None:
        with self._lock:
            username = self._tokens.get(token)
            return _public_user(self._users[username]) if username else None

    def logout(self, token: str) -> None:
        with self._lock:
            self._tokens.pop(token, None)

    # ---------- videos ----------

    def _find_video(self, video_id: str) -> dict | None:
        return next((v for v in self._videos if v["id"] == video_id), None)

    def list_videos(self) -> list[dict]:
        with self._lock:
            return [dict(v) for v in self._videos]

    def get_video(self, video_id: str) -> dict | None:
        with self._lock:
            video = self._find_video(video_id)
            return dict(video) if video else None

    def create_video(self, user: dict, title: str, caption: str) -> dict:
        with self._lock:
            self._video_counter += 1
            video = {
                "id": f"v_{self._video_counter}",
                "title": title,
                "caption": caption,
                "creator": {
                    "username": user["username"],
                    "displayName": user["displayName"],
                    "initials": user["initials"],
                    "color": user["color"],
                },
                "tone": "#27272a",
                "sound": "Original sound",
                "tags": [],
                "status": "processing",
                "likeCount": 0,
                "createdAt": utc_now(),
                "transcript": [],
            }
            self._videos.insert(0, video)
            return dict(video)

    def mark_ready(self, video_id: str, transcript: list[str]) -> None:
        with self._lock:
            video = self._find_video(video_id)
            if video:
                video["status"] = "ready"
                video["tone"] = "#1f2a37"
                video["transcript"] = list(transcript)

    # ---------- comments ----------

    def list_comments(self, video_id: str) -> list[dict]:
        with self._lock:
            found = [dict(c) for c in self._comments if c["videoId"] == video_id]
        return sorted(found, key=lambda c: c["createdAt"])

    def add_comment(self, video_id: str, user: dict, text: str) -> dict:
        with self._lock:
            self._comment_counter += 1
            comment = {
                "id": f"c_{self._comment_counter}",
                "videoId": video_id,
                "username": user["username"],
                "initials": user["initials"],
                "color": user["color"],
                "text": text,
                "createdAt": utc_now(),
                "sentiment": analyse(text),
            }
            self._comments.append(comment)
            return dict(comment)

    # ---------- likes ----------

    def like(self, video_id: str, username: str) -> tuple[bool, int] | None:
        with self._lock:
            video = self._find_video(video_id)
            if video is None:
                return None
            key = (video_id, username)
            if key not in self._likes:
                self._likes.add(key)
                video["likeCount"] += 1
            return True, video["likeCount"]

    def unlike(self, video_id: str, username: str) -> tuple[bool, int] | None:
        with self._lock:
            video = self._find_video(video_id)
            if video is None:
                return None
            key = (video_id, username)
            if key in self._likes:
                self._likes.remove(key)
                video["likeCount"] -= 1
            return False, video["likeCount"]
