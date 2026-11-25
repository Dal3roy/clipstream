"""Tests for upload names and upload links. These run offline: no Azure account is needed."""
import base64

from app.blob import upload_blob_name, upload_url


def test_blob_name_keeps_a_safe_extension():
    assert upload_blob_name("v_1", "My Clip.MP4") == "v_1/original.mp4"
    assert upload_blob_name("v_1", "no-extension") == "v_1/original"


def test_upload_url_is_a_write_only_link_for_one_blob():
    key = base64.b64encode(b"k" * 32).decode()  # a fake key, only used to sign the link
    url = upload_url("cosdbcw", key, "raw-uploads", "v_1/original.mp4")
    assert url.startswith("https://cosdbcw.blob.core.windows.net/raw-uploads/v_1/original.mp4?")
    assert "sig=" in url
    assert "sp=cw" in url  # create and write only, no read or delete
