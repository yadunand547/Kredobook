"""
Storage utility for secure file uploads (Payment Screenshots).

Handles:
- Secure unique filename generation
- File type validation (PNG, JPEG, WEBP)
- File size validation (Max 5MB)
- Path traversal protection
- Local directory persistence with configurable paths
"""

import os
import uuid
from pathlib import Path
from fastapi import HTTPException, UploadFile, status

# Configuration
UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "uploads" / "screenshots"
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
ALLOWED_CONTENT_TYPES = {
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp",
}


def ensure_upload_dir() -> Path:
    """Ensure upload directory exists on disk."""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    return UPLOAD_DIR


async def save_screenshot(file: UploadFile) -> str:
    """
    Validate and save an uploaded screenshot file.

    Returns the unique saved filename (e.g. 'a8f9b2...png').
    Raises HTTPException on validation failure.
    """
    if not file or not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment screenshot file is required",
        )

    # 1. Validate extension
    original_filename = file.filename
    ext = os.path.splitext(original_filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{ext}'. Allowed formats: PNG, JPG, JPEG, WEBP",
        )

    # 2. Validate content-type header
    content_type = (file.content_type or "").lower()
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid MIME type '{content_type}'. Must be an image (PNG, JPEG, WEBP)",
        )

    # 3. Read content and validate file size
    content = await file.read()
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )

    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size exceeds maximum allowed limit of {MAX_FILE_SIZE_BYTES // (1024 * 1024)}MB",
        )

    # 4. Generate unique filename (never trust original filename)
    unique_filename = f"{uuid.uuid4().hex}{ext}"

    # 5. Save to upload directory
    upload_dir = ensure_upload_dir()
    destination = upload_dir / unique_filename

    with open(destination, "wb") as f:
        f.write(content)

    return unique_filename


def get_screenshot_path(filename: str) -> Path:
    """
    Resolve and validate path for a screenshot filename.
    Guards against directory traversal attacks.
    """
    if not filename:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Screenshot not found",
        )

    # Sanitize: extract base name only
    clean_name = os.path.basename(filename)
    upload_dir = ensure_upload_dir().resolve()
    target_path = (upload_dir / clean_name).resolve()

    # Path traversal check
    if not str(target_path).startswith(str(upload_dir)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file path",
        )

    if not target_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Screenshot file does not exist",
        )

    return target_path
