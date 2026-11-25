"""API tests. Run from the backend folder with:  pytest"""
import pytest
from fastapi.testclient import TestClient

from app.config import offline_settings
from app.main import create_app
from app.store import DEMO_EMAIL, DEMO_PASSWORD, SEED_PATH, Store


@pytest.fixture
def client():
    # A fresh in-memory store for every test, with Azure switched off so tests never touch real services.
    return TestClient(create_app(Store.from_seed_file(SEED_PATH), offline_settings()))


def auth_headers(client, email=DEMO_EMAIL, password=DEMO_PASSWORD):
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


def test_lists_seed_videos(client):
    response = client.get("/api/videos")
    assert response.status_code == 200
    assert len(response.json()) >= 3


def test_unknown_video_returns_404(client):
    response = client.get("/api/videos/does-not-exist")
    assert response.status_code == 404
    assert response.json()["detail"] == "Video not found"


def test_login_rejects_wrong_password(client):
    response = client.post("/api/auth/login", json={"email": DEMO_EMAIL, "password": "wrong-password"})
    assert response.status_code == 401


def test_signup_then_login(client):
    signup = client.post("/api/auth/signup", json={
        "name": "Test Person", "email": "test.person@example.com", "password": "longenough1",
    })
    assert signup.status_code == 201
    assert signup.json()["username"] == "test.person"

    login = client.post("/api/auth/login", json={"email": "test.person@example.com", "password": "longenough1"})
    assert login.status_code == 200


def test_signup_rejects_duplicate_email(client):
    response = client.post("/api/auth/signup", json={
        "name": "Demo Again", "email": DEMO_EMAIL, "password": "longenough1",
    })
    assert response.status_code == 409


def test_comment_requires_login(client):
    response = client.post("/api/videos/v_1042/comments", json={"text": "Nice"})
    assert response.status_code == 401


def test_comment_gets_sentiment_and_is_listed(client):
    headers = auth_headers(client)
    posted = client.post("/api/videos/v_1042/comments", json={"text": "I love this, it is amazing"}, headers=headers)
    assert posted.status_code == 201
    assert posted.json()["sentiment"]["label"] == "positive"

    listed = client.get("/api/videos/v_1042/comments").json()
    assert any(c["id"] == posted.json()["id"] for c in listed)


def test_empty_comment_is_rejected(client):
    headers = auth_headers(client)
    response = client.post("/api/videos/v_1042/comments", json={"text": "   "}, headers=headers)
    assert response.status_code == 422


def test_like_counts_once_and_unlike_reduces(client):
    headers = auth_headers(client)
    start = client.get("/api/videos/v_1043").json()["likeCount"]

    first = client.post("/api/videos/v_1043/like", headers=headers).json()
    second = client.post("/api/videos/v_1043/like", headers=headers).json()
    assert first == {"liked": True, "likeCount": start + 1}
    assert second == {"liked": True, "likeCount": start + 1}

    removed = client.delete("/api/videos/v_1043/like", headers=headers).json()
    assert removed == {"liked": False, "likeCount": start}


def test_upload_rejects_non_video(client):
    headers = auth_headers(client)
    response = client.post("/api/videos/upload-url", headers=headers, json={
        "title": "Not a video", "caption": "", "fileName": "notes.pdf",
        "contentType": "application/pdf", "sizeBytes": 1000,
    })
    assert response.status_code == 422


def test_upload_creates_processing_video_then_ready(client):
    headers = auth_headers(client)
    response = client.post("/api/videos/upload-url", headers=headers, json={
        "title": "My clip", "caption": "test", "fileName": "clip.mp4",
        "contentType": "video/mp4", "sizeBytes": 1000,
    })
    assert response.status_code == 201
    video_id = response.json()["videoId"]
    assert client.get(f"/api/videos/{video_id}").json()["status"] == "processing"

    upload = client.put(f"/api/mock-blob/{video_id}", content=b"x" * 1000)
    assert upload.status_code == 201
    assert upload.json() == {"received": 1000}
