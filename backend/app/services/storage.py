"""Where uploaded files live. LocalStorage writes to a folder on disk.

The rest of the code only uses `save`, `path` and `delete`, so you can add an
S3Storage class with the same methods later (see the exercises in LEARNING_GUIDE.md).
"""

import uuid
from pathlib import Path

from app.core.config import settings


class LocalStorage:
    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = Path(base_dir or settings.upload_dir)

    def new_name(self, extension: str) -> str:
        # Never use the user's filename on disk: it could contain "../" or clash.
        return f"{uuid.uuid4().hex}{extension}"

    def path(self, stored_name: str) -> Path:
        return self.base_dir / stored_name

    def open_for_write(self, stored_name: str):  # type: ignore[no-untyped-def]
        self.base_dir.mkdir(parents=True, exist_ok=True)
        return self.path(stored_name).open("wb")

    def delete(self, stored_name: str) -> None:
        self.path(stored_name).unlink(missing_ok=True)
