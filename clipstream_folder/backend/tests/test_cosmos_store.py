"""Tests against the real Cosmos DB. They are skipped unless you set these in backend/.env:

    COSMOS_URI, COSMOS_KEY, and COSMOS_TEST_DATABASE (a database for tests, not your live data)

Run with:  python -m pytest tests/test_cosmos_store.py
"""
import os
import secrets

import pytest

from app.config import load_settings
from app.cosmos_store import CosmosStore

settings = load_settings()
TEST_DATABASE = os.getenv("COSMOS_TEST_DATABASE")

pytestmark = pytest.mark.skipif(
    not (settings.use_cosmos and TEST_DATABASE),
    reason="needs COSMOS_URI, COSMOS_KEY and COSMOS_TEST_DATABASE",
)


@pytest.fixture
def store():
    return CosmosStore(settings.cosmos_uri, settings.cosmos_key, TEST_DATABASE)


def test_like_counts_once_and_unlike_reduces(store):
    email = f"tester{secrets.token_hex(4)}@example.com"
    user = store.signup("Tester", email, "longenough1")
    video = store.create_video(user, "Test clip", "test")

    assert store.like(video["id"], user["username"]) == (True, 1)
    assert store.like(video["id"], user["username"]) == (True, 1)  # second like changes nothing
    assert store.unlike(video["id"], user["username"]) == (False, 0)


def test_comment_is_saved_with_sentiment(store):
    email = f"tester{secrets.token_hex(4)}@example.com"
    user = store.signup("Tester", email, "longenough1")
    video = store.create_video(user, "Test clip", "test")

    comment = store.add_comment(video["id"], user, "I love this, it is amazing")
    assert comment["sentiment"]["label"] == "positive"
    assert any(c["id"] == comment["id"] for c in store.list_comments(video["id"]))
