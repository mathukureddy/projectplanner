"""Local file storage root for task attachments."""
from pathlib import Path

UPLOAD_ROOT = Path(__file__).resolve().parent / "uploads"
