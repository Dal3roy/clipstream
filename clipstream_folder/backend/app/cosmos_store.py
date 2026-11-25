"""Cosmos DB version of the store.

Same methods as store.Store, so the routes in main.py work unchanged.

Containers in the SharedDB database:
  videos   partition key /id
  comments partition key /videoId
  likes    partition key /videoId
  users    partition key /id

Login sessions are still kept in memory, so users log in again after a restart.
"""
from __future__ import annotations

import secrets

from azure.cosmos import CosmosClient, exceptions

from .sentiment import analyse
from .store import (
    AVATAR_COLOURS,
    DEMO_EMAIL,
    DEMO_NAME,
    DEMO_PASSWORD,
    _hash_password,
    _initials,
    _public_user,
    utc_now,
)


class CosmosStore:
    def __init__(self, uri: str, key: str, database_name: str = "SharedDB"):
        client = CosmosClient(uri, credential=key)
        database = client.get_database_client(database_name)
        self.videos = database.get_container_client("videos")
        self.comments = database.get_container_client("comments")
        self.likes = database.get_container_client("likes")
        self.users = database.get_container_client("users")
        self._tokens: dict[str, str] = {}  # session token -> username
        try:
            self._create_user(DEMO_NAME, DEMO_EMAIL, DEMO_PASSWORD)
        except ValueError:
            pass  # demo account already exists

    # ---------- users and sessions ----------

    def _get_user(self, username: str) -> dict | None:
        try:
            return self.users.read_item(item=username, partition_key=username)
        except exceptions.CosmosResourceNotFoundError:
            return None

    def _create_user(self, name: str, email: str, password: str) -> dict:
        username = email.split("@")[0].lower()
        salt = secrets.token_bytes(16)
        user = {
            "id": username,
            "username": username,
            "displayName": name,
            "initials": _initials(name),
            "color": AVATAR_COLOURS[sum(map(ord, username)) % len(AVATAR_COLOURS)],
            "salt": salt.hex(),  # stored as text, because Cosmos documents are JSON
            "passwordHash": _hash_password(password, salt),
        }
        try:
            self.users.create_item(body=user)
        except exceptions.CosmosResourceExistsError:
            raise ValueError("An account with that email already exists.")
        return user

    def _new_session(self, user: dict) -> dict:
        token = secrets.token_urlsafe(24)
        self._tokens[token] = user["username"]
        return {**_public_user(user), "token": token}

    def signup(self, name: str, email: str, password: str) -> dict:
        return self._new_session(self._create_user(name, email, password))

    def login(self, email: str, password: str) -> dict | None:
        username = email.split("@")[0].lower()
        user = self._get_user(username)
        if user is None:
            return None
        salt = bytes.fromhex(user["salt"])
        if not secrets.compare_digest(_hash_password(password, salt), user["passwordHash"]):
            return None
        return self._new_session(user)

    def user_for_token(self, token: str) -> dict | None:
        username = self._tokens.get(token)
        if username is None:
            return None
        user = self._get_user(username)
        return _public_user(user) if user else None

    def logout(self, token: str) -> None:
        self._tokens.pop(token, None)

    # ---------- videos ----------

    def list_videos(self) -> list[dict]:
        return list(self.videos.query_items(
            query="SELECT * FROM c ORDER BY c.createdAt DESC",
            enable_cross_partition_query=True,
        ))

    def get_video(self, video_id: str) -> dict | None:
        try:
            return self.videos.read_item(item=video_id, partition_key=video_id)
        except exceptions.CosmosResourceNotFoundError:
            return None

    def create_video(self, user: dict, title: str, caption: str) -> dict:
        video = {
            "id": f"v_{secrets.token_hex(4)}",
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
        self.videos.create_item(body=video)
        return video

    def mark_ready(self, video_id: str, transcript: list[str]) -> None:
        self.videos.patch_item(
            item=video_id,
            partition_key=video_id,
            patch_operations=[
                {"op": "set", "path": "/status", "value": "ready"},
                {"op": "set", "path": "/transcript", "value": list(transcript)},
            ],
        )

    # ---------- comments ----------

    def list_comments(self, video_id: str) -> list[dict]:
        return list(self.comments.query_items(
            query="SELECT * FROM c WHERE c.videoId = @videoId ORDER BY c.createdAt ASC",
            parameters=[{"name": "@videoId", "value": video_id}],
            partition_key=video_id,
        ))

    def add_comment(self, video_id: str, user: dict, text: str) -> dict:
        comment = {
            "id": f"c_{secrets.token_hex(6)}",
            "videoId": video_id,
            "username": user["username"],
            "initials": user["initials"],
            "color": user["color"],
            "text": text,
            "createdAt": utc_now(),
            "sentiment": analyse(text),
        }
        self.comments.create_item(body=comment)
        return comment

    # ---------- likes ----------

    def _adjust_count(self, video_id: str, delta: int) -> int:
        # Cosmos applies the increment on the server, so two likes at once can't lose an update.
        updated = self.videos.patch_item(
            item=video_id,
            partition_key=video_id,
            patch_operations=[{"op": "incr", "path": "/likeCount", "value": delta}],
        )
        return updated["likeCount"]

    def like(self, video_id: str, username: str) -> tuple[bool, int] | None:
        video = self.get_video(video_id)
        if video is None:
            return None
        like_doc = {
            "id": f"{video_id}:{username}",  # one like per user per video
            "videoId": video_id,
            "userId": username,
            "createdAt": utc_now(),
        }
        try:
            self.likes.create_item(body=like_doc)
        except exceptions.CosmosResourceExistsError:
            return True, video["likeCount"]  # already liked: count unchanged
        return True, self._adjust_count(video_id, 1)

    def unlike(self, video_id: str, username: str) -> tuple[bool, int] | None:
        video = self.get_video(video_id)
        if video is None:
            return None
        try:
            self.likes.delete_item(item=f"{video_id}:{username}", partition_key=video_id)
        except exceptions.CosmosResourceNotFoundError:
            return False, video["likeCount"]  # was not liked: count unchanged
        return False, self._adjust_count(video_id, -1)

    # ---------- seeding ----------

    def seed(self, data: dict) -> bool:
        """Load the sample data, but only if the videos container is empty."""
        if list(self.videos.query_items(query="SELECT TOP 1 c.id FROM c", enable_cross_partition_query=True)):
            return False
        for video in data["videos"]:
            self.videos.upsert_item(body=video)
        for comment in data["comments"]:
            comment = {**comment, "sentiment": analyse(comment["text"])}
            self.comments.upsert_item(body=comment)
        return True
