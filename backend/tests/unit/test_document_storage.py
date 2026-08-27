import hashlib
from io import BytesIO
from pathlib import Path

import pytest
from fastapi import UploadFile
from starlette.datastructures import Headers

from app.core.exceptions import (
    DocumentTooLargeError,
    EmptyDocumentError,
    UnsupportedDocumentTypeError,
)
from app.services.document_storage import DocumentStorageService


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def make_upload(
    filename: str,
    content: bytes,
    content_type: str = "text/plain",
) -> UploadFile:
    return UploadFile(
        file=BytesIO(content),
        filename=filename,
        headers=Headers({"content-type": content_type}),
    )


@pytest.mark.anyio
async def test_store_document(tmp_path: Path) -> None:
    content = b"Knowledge assistant test document."
    service = DocumentStorageService(
        storage_path=tmp_path,
        max_size_bytes=1024,
        allowed_extensions=(".txt",),
    )
    upload = make_upload("example.txt", content)

    stored = await service.store(upload)

    assert stored.original_filename == "example.txt"
    assert stored.stored_filename.endswith(".txt")
    assert stored.file_path == stored.stored_filename
    assert stored.file_size == len(content)
    assert stored.checksum == hashlib.sha256(content).hexdigest()
    assert stored.mime_type == "text/plain"

    saved_path = tmp_path / stored.file_path

    assert saved_path.exists()
    assert saved_path.read_bytes() == content

    service.delete(stored.file_path)

    assert not saved_path.exists()


@pytest.mark.anyio
async def test_reject_unsupported_extension(
    tmp_path: Path,
) -> None:
    service = DocumentStorageService(
        storage_path=tmp_path,
        allowed_extensions=(".txt",),
    )
    upload = make_upload("malware.exe", b"content")

    with pytest.raises(UnsupportedDocumentTypeError):
        await service.store(upload)

    assert not any(tmp_path.iterdir())


@pytest.mark.anyio
async def test_reject_oversized_document(
    tmp_path: Path,
) -> None:
    service = DocumentStorageService(
        storage_path=tmp_path,
        max_size_bytes=4,
        allowed_extensions=(".txt",),
    )
    upload = make_upload("large.txt", b"12345")

    with pytest.raises(DocumentTooLargeError):
        await service.store(upload)

    assert not any(tmp_path.iterdir())


@pytest.mark.anyio
async def test_reject_empty_document(
    tmp_path: Path,
) -> None:
    service = DocumentStorageService(
        storage_path=tmp_path,
        allowed_extensions=(".txt",),
    )
    upload = make_upload("empty.txt", b"")

    with pytest.raises(EmptyDocumentError):
        await service.store(upload)

    assert not any(tmp_path.iterdir())


@pytest.mark.anyio
async def test_sanitize_uploaded_filename(
    tmp_path: Path,
) -> None:
    service = DocumentStorageService(
        storage_path=tmp_path,
        allowed_extensions=(".txt",),
    )
    upload = make_upload(
        "../../nested/unsafe.txt",
        b"safe content",
    )

    stored = await service.store(upload)

    assert stored.original_filename == "unsafe.txt"
    assert (tmp_path / stored.file_path).exists()


def test_reject_delete_path_traversal(
    tmp_path: Path,
) -> None:
    storage_path = tmp_path / "storage"
    storage_path.mkdir()

    outside_file = tmp_path / "outside.txt"
    outside_file.write_text("must remain", encoding="utf-8")

    service = DocumentStorageService(
        storage_path=storage_path,
    )

    with pytest.raises(ValueError):
        service.delete("../outside.txt")

    assert outside_file.exists()