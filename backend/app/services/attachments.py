"""File attachments: validated, size-limited uploads stored with LocalStorage.

Validation, in order:
  1. the extension must be on the allow-list below
  2. the first bytes must match the format ("magic numbers"), so a renamed .exe
     cannot pretend to be a .png
  3. the file is streamed to disk in chunks and rejected as soon as it passes 10 MB
     (we never hold the whole file in memory)
The Content-Type we store comes from our allow-list, not from the client.
"""

from pathlib import Path

from fastapi import UploadFile
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import NotFoundError, PayloadTooLargeError, UnsupportedMediaTypeError
from app.models import Attachment, User
from app.realtime.events import EventPublisher
from app.repositories.boards import BoardRepository
from app.repositories.collaboration import AttachmentRepository
from app.repositories.tasks import TaskRepository
from app.schemas.collaboration import AttachmentOut
from app.services.activity import ActivityService
from app.services.storage import LocalStorage

CHUNK_SIZE = 1024 * 1024

ALLOWED_TYPES: dict[str, str] = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".csv": "text/csv",
    ".zip": "application/zip",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}

ZIP = (b"PK\x03\x04", b"PK\x05\x06")
SIGNATURES: dict[str, tuple[bytes, ...]] = {
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".gif": (b"GIF87a", b"GIF89a"),
    ".pdf": (b"%PDF-",),
    ".zip": ZIP,
    ".docx": ZIP,  # Office files are zip archives
    ".xlsx": ZIP,
}
TEXT_TYPES = {".txt", ".md", ".csv"}


def check_signature(extension: str, head: bytes) -> bool:
    if extension == ".webp":
        return head[:4] == b"RIFF" and head[8:12] == b"WEBP"
    if extension in TEXT_TYPES:
        if b"\x00" in head:
            return False
        try:
            head.decode("utf-8")
        except UnicodeDecodeError as exc:
            # The chunk may end in the middle of a multi-byte character; that's fine.
            return exc.start >= len(head) - 3
        return True
    return head.startswith(SIGNATURES[extension])


class AttachmentService:
    def __init__(self, session: AsyncSession, redis: Redis) -> None:
        self.session = session
        self.repo = AttachmentRepository(session)
        self.tasks = TaskRepository(session)
        self.boards = BoardRepository(session)
        self.activity = ActivityService(session)
        self.events = EventPublisher(redis)
        self.storage = LocalStorage()

    async def list_for_task(
        self, task_id: int, limit: int, offset: int
    ) -> tuple[list[Attachment], int]:
        return await self.repo.list_for_task(task_id, limit, offset)

    async def upload(self, task_id: int, upload: UploadFile, actor: User) -> Attachment:
        task = await self.tasks.get(task_id)
        if task is None:
            raise NotFoundError("Task not found")
        filename = Path(upload.filename or "file").name[:255]
        extension = Path(filename).suffix.lower()
        if extension not in ALLOWED_TYPES:
            allowed = ", ".join(sorted(ALLOWED_TYPES))
            raise UnsupportedMediaTypeError(f"File type not allowed. Allowed: {allowed}")
        if upload.size is not None and upload.size > settings.max_upload_bytes:
            raise PayloadTooLargeError(self._too_large_message())

        stored_name = self.storage.new_name(extension)
        size = 0
        try:
            with self.storage.open_for_write(stored_name) as out:
                first = True
                while chunk := await upload.read(CHUNK_SIZE):
                    if first:
                        if not check_signature(extension, chunk[:2048]):
                            raise UnsupportedMediaTypeError(
                                f"The file content does not look like a {extension} file",
                                "file_content_mismatch",
                            )
                        first = False
                    size += len(chunk)
                    if size > settings.max_upload_bytes:
                        raise PayloadTooLargeError(self._too_large_message())
                    out.write(chunk)
            if size == 0:
                raise UnsupportedMediaTypeError("The file is empty", "empty_file")
        except BaseException:
            self.storage.delete(stored_name)  # never leave half-written files behind
            raise

        board = await self.boards.get(task.board_id)
        assert board is not None
        attachment = await self.repo.add(
            Attachment(
                task_id=task_id,
                uploader_id=actor.id,
                filename=filename,
                stored_name=stored_name,
                content_type=ALLOWED_TYPES[extension],
                size=size,
            )
        )
        await self.activity.record(
            workspace_id=board.workspace_id,
            user_id=actor.id,
            board_id=board.id,
            task_id=task_id,
            action="attachment.created",
            summary=f"attached '{filename}' to '{task.title}'",
        )
        await self.session.commit()
        await self.events.publish(
            board.id,
            "attachment.created",
            AttachmentOut.model_validate(attachment).model_dump(mode="json"),
            actor.id,
        )
        return attachment

    async def get_file(self, attachment_id: int) -> tuple[Attachment, Path]:
        attachment = await self.repo.get(attachment_id)
        if attachment is None:
            raise NotFoundError("Attachment not found")
        path = self.storage.path(attachment.stored_name)
        if not path.exists():
            raise NotFoundError("The file is missing from storage", "file_missing")
        return attachment, path

    async def delete(self, attachment_id: int, actor: User) -> None:
        attachment = await self.repo.get(attachment_id)
        if attachment is None:
            raise NotFoundError("Attachment not found")
        task = await self.tasks.get(attachment.task_id)
        assert task is not None
        stored_name = attachment.stored_name
        await self.repo.delete(attachment)
        await self.session.commit()
        self.storage.delete(stored_name)
        await self.events.publish(
            task.board_id,
            "attachment.deleted",
            {"id": attachment_id, "task_id": task.id},
            actor.id,
        )

    @staticmethod
    def _too_large_message() -> str:
        return f"File is larger than {settings.max_upload_bytes // (1024 * 1024)} MB"
