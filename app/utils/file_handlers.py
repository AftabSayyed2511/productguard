import os
import uuid
from pathlib import Path
from PIL import Image
from werkzeug.utils import secure_filename
from flask import current_app

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png"}


def allowed_file(filename: str) -> bool:
    """Check if the filename extension is supported."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def validate_and_save_image(
    file_storage, target_directory: str, max_size_bytes: int = 5 * 1024 * 1024
) -> tuple[bool, str, str]:
    """
    Validate an uploaded image for binary integrity, dimension safety, and format.
    Saves to target_directory with a secure random UUID filename.

    Returns:
        tuple (success: bool, saved_filename_or_error: str, original_filename: str)
    """
    if not file_storage or file_storage.filename == "":
        return False, "No file selected.", ""

    orig_filename = secure_filename(file_storage.filename)
    if not allowed_file(orig_filename):
        return (
            False,
            "Unsupported file format. Only JPEG, JPG, and PNG are permitted.",
            orig_filename,
        )

    # Check file size (seek to end, read length, seek back to 0)
    file_storage.seek(0, os.SEEK_END)
    file_size = file_storage.tell()
    file_storage.seek(0)

    if file_size > max_size_bytes:
        return False, "File exceeds maximum permitted size of 5 MB.", orig_filename

    # Validate image content using Pillow (inspect binary magic bytes)
    try:
        image = Image.open(file_storage)
        image.verify()  # Verifies file integrity without decoding full image
        file_storage.seek(0)  # Reset stream after verify()
    except Exception:
        return False, "Corrupted image file or invalid image headers.", orig_filename

    # Re-open to inspect dimensions
    try:
        image = Image.open(file_storage)
        width, height = image.size
        if width < 32 or height < 32:
            return (
                False,
                f"Image dimensions too small ({width}x{height}). Minimum is 32x32.",
                orig_filename,
            )
        file_storage.seek(0)
    except Exception:
        return False, "Failed to decode image dimensions.", orig_filename

    # Generate secure random UUID filename to prevent collision and path traversal
    ext = orig_filename.rsplit(".", 1)[1].lower()
    if ext == "jpeg":
        ext = "jpg"
    unique_filename = f"{uuid.uuid4().hex}.{ext}"

    # Ensure target directory exists
    os.makedirs(target_directory, exist_ok=True)
    destination_path = os.path.join(target_directory, unique_filename)

    file_storage.save(destination_path)
    return True, unique_filename, orig_filename


def delete_file_safe(file_path: str) -> bool:
    """Safely delete a file from disk if it exists."""
    if not file_path:
        return False
    try:
        p = Path(file_path)
        if p.exists() and p.is_file():
            p.unlink()
            return True
    except Exception:
        pass
    return False
