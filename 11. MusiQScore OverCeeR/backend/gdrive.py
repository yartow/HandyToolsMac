#!/usr/bin/env python3

"""
Google Drive upload helper using a service account (headless, no OAuth dance).
All functions return empty string on failure — Drive upload is non-fatal.
"""

from pathlib import Path

from google.auth.exceptions import GoogleAuthError
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def _service(credentials_path: str):
    creds = service_account.Credentials.from_service_account_file(
        credentials_path, scopes=SCOPES
    )
    return build("drive", "v3", credentials=creds)


def upload_file(file_path: Path, folder_id: str, credentials_path: str) -> str:
    """
    Upload file_path to the given Drive folder.
    Returns the webViewLink on success, empty string on any error.
    """
    try:
        service = _service(credentials_path)
        metadata = {"name": file_path.name, "parents": [folder_id]}
        media = MediaFileUpload(str(file_path), resumable=True)
        result = (
            service.files()
            .create(body=metadata, media_body=media, fields="id,webViewLink")
            .execute()
        )
        return result.get("webViewLink", "")
    except (GoogleAuthError, HttpError, FileNotFoundError, Exception) as e:
        print(f"      Drive upload failed for {file_path.name}: {e}")
        return ""
