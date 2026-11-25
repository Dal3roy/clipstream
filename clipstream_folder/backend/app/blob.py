"""Short-lived upload links (SAS) for the raw-uploads container.

The browser uploads straight to Blob Storage using one of these links. The API never
receives the video bytes, and the storage key never leaves the server.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from azure.storage.blob import BlobSasPermissions, generate_blob_sas

UPLOAD_LINK_MINUTES = 15


def upload_blob_name(video_id: str, file_name: str) -> str:
    """For example 'v_123/original.mp4'. Keeps the extension, drops anything unsafe."""
    match = re.search(r"\.([A-Za-z0-9]{1,8})$", file_name)
    extension = f".{match.group(1).lower()}" if match else ""
    return f"{video_id}/original{extension}"


def upload_url(account: str, key: str, container: str, blob_name: str) -> str:
    """A link that allows one blob to be created or overwritten, for a short time only."""
    expiry = datetime.now(timezone.utc) + timedelta(minutes=UPLOAD_LINK_MINUTES)
    token = generate_blob_sas(
        account_name=account,
        container_name=container,
        blob_name=blob_name,
        account_key=key,
        permission=BlobSasPermissions(create=True, write=True),
        expiry=expiry,
    )
    return f"https://{account}.blob.core.windows.net/{container}/{blob_name}?{token}"
