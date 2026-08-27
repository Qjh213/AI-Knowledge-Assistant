import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.core.config import settings
from app.core.exceptions import (
    DocumentTooLargeError,
    EmptyDocumentError,
    UnsupportedDocumentTypeError,
)


READ_CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True, slots=True)
class StoredDocument:
    original_filename: str
    stored_filename: str
    file_path: str
    mime_type: str
    file_size: int
    checksum: str


class DocumentStorageService:
    def __init__(
        self,
        storage_path: Path | None = None,
        max_size_bytes: int | None = None,
        allowed_extensions: tuple[str, ...] | None = None,
    ) -> None:
        self.storage_path = (
            storage_path or settings.document_storage_path
        ).resolve()
        self.max_size_bytes = (
            max_size_bytes
            if max_size_bytes is not None
            else settings.max_upload_size_bytes
        )
        self.allowed_extensions = {
            extension.lower()
            for extension in (
                allowed_extensions
                or settings.allowed_document_extensions
            )
        }

    async def store(self, upload: UploadFile) -> StoredDocument:
        original_filename = self._sanitize_filename(
            upload.filename
        )
        extension = Path(original_filename).suffix.lower()

        if extension not in self.allowed_extensions:
            raise UnsupportedDocumentTypeError(extension)

        self.storage_path.mkdir(parents=True, exist_ok=True)

        stored_filename = f"{uuid4().hex}{extension}"
        destination = self.storage_path / stored_filename
        temporary = self.storage_path / f".{stored_filename}.part"

        checksum = hashlib.sha256()
        file_size = 0

        try:
            with temporary.open("wb") as output:
                while chunk := await upload.read(READ_CHUNK_SIZE):
                    file_size += len(chunk)

                    if file_size > self.max_size_bytes:
                        raise DocumentTooLargeError(
                            settings.max_upload_size_mb
                        )

                    checksum.update(chunk)
                    output.write(chunk)

            if file_size == 0:
                raise EmptyDocumentError()

            os.replace(temporary, destination)

            return StoredDocument(
                original_filename=original_filename,
                stored_filename=stored_filename,
                file_path=stored_filename,
                mime_type=(
                    upload.content_type
                    or "application/octet-stream"
                ),
                file_size=file_size,
                checksum=checksum.hexdigest(),
            )

        except Exception:
            temporary.unlink(missing_ok=True)
            destination.unlink(missing_ok=True)
            raise

    def delete(self, file_path: str) -> None:
        target = (self.storage_path / file_path).resolve()

        if (
            target != self.storage_path
            and self.storage_path not in target.parents
        ):
            raise ValueError("Invalid document storage path")

        target.unlink(missing_ok=True)

    @staticmethod
    def _sanitize_filename(filename: str | None) -> str:
        if not filename:
            raise UnsupportedDocumentTypeError("")

        normalized = filename.replace("\\", "/")
        return Path(normalized).name