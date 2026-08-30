from pathlib import Path
from io import BytesIO
from zipfile import ZipFile

import httpx
import pytest

from app.core.exceptions import MinerUServiceError
from app.services.mineru import MinerUClient


def make_client(handler) -> MinerUClient:
    transport = httpx.MockTransport(handler)
    return MinerUClient(
        client=httpx.Client(transport=transport),
        api_token="test-token",
        base_url="https://mineru.example/api/v4",
    )


def test_request_upload_url() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v4/file-urls/batch"
        assert request.headers["Authorization"] == "Bearer test-token"
        payload = __import__("json").loads(request.content)
        assert payload["files"] == [{"name": "lesson.pdf", "is_ocr": True}]
        assert payload["model_version"] == "vlm"
        return httpx.Response(
            200,
            json={
                "code": 0,
                "data": {
                    "batch_id": "batch-1",
                    "file_urls": ["https://upload.example/signed"],
                },
            },
        )

    task = make_client(handler).request_upload_url("lesson.pdf")

    assert task.batch_id == "batch-1"
    assert task.upload_url == "https://upload.example/signed"


def test_upload_file(tmp_path: Path) -> None:
    file_path = tmp_path / "lesson.pdf"
    file_path.write_bytes(b"pdf-content")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "PUT"
        assert request.url == httpx.URL("https://upload.example/signed")
        assert request.content == b"pdf-content"
        assert "Authorization" not in request.headers
        return httpx.Response(200)

    make_client(handler).upload_file(
        "https://upload.example/signed",
        file_path,
    )


def test_get_running_batch_result() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v4/extract-results/batch/batch-1"
        return httpx.Response(
            200,
            json={
                "code": 0,
                "data": {
                    "batch_id": "batch-1",
                    "extract_result": [
                        {
                            "file_name": "lesson.pdf",
                            "state": "running",
                            "extract_progress": {
                                "extracted_pages": 3,
                                "total_pages": 10,
                            },
                        }
                    ],
                },
            },
        )

    result = make_client(handler).get_batch_result("batch-1")

    assert result.state == "running"
    assert result.progress == 30
    assert result.full_zip_url is None


def test_get_completed_batch_result() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "code": 0,
                "data": {
                    "extract_result": [
                        {
                            "file_name": "lesson.pdf",
                            "state": "done",
                            "full_zip_url": "https://download.example/result.zip",
                        }
                    ]
                },
            },
        )

    result = make_client(handler).get_batch_result("batch-1")

    assert result.state == "done"
    assert result.progress == 100
    assert result.full_zip_url == "https://download.example/result.zip"


def test_wrap_api_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"code": 400, "msg": "invalid token", "data": {}},
        )

    with pytest.raises(MinerUServiceError, match="invalid token"):
        make_client(handler).request_upload_url("lesson.pdf")


def test_reject_missing_token() -> None:
    with pytest.raises(MinerUServiceError, match="MINERU_API_TOKEN"):
        MinerUClient(
            client=httpx.Client(),
            api_token=" ",
            base_url="https://mineru.example/api/v4",
        )


def test_reject_path_as_remote_file_name() -> None:
    client = make_client(lambda request: httpx.Response(500))

    with pytest.raises(MinerUServiceError, match="invalid upload file name"):
        client.request_upload_url("folder/lesson.pdf")


def create_zip(entries: dict[str, bytes]) -> bytes:
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return output.getvalue()


def test_download_markdown_from_result_zip() -> None:
    result_zip = create_zip(
        {
            "images/page-1.png": b"image",
            "result/full.md": "# 标题\n\n正文".encode(),
        }
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == httpx.URL(
            "https://download.example/result.zip"
        )
        assert "Authorization" not in request.headers
        return httpx.Response(200, content=result_zip)

    markdown = make_client(handler).download_markdown(
        "https://download.example/result.zip"
    )

    assert markdown == "# 标题\n\n正文"


def test_reject_result_zip_without_full_markdown() -> None:
    result_zip = create_zip({"result/content.md": b"content"})

    with pytest.raises(MinerUServiceError, match="exactly one full.md"):
        make_client(
            lambda request: httpx.Response(200, content=result_zip)
        ).download_markdown("https://download.example/result.zip")


def test_reject_oversized_result_download() -> None:
    with pytest.raises(MinerUServiceError, match="download size limit"):
        make_client(
            lambda request: httpx.Response(200, content=b"too large")
        ).download_markdown(
            "https://download.example/result.zip",
            max_download_bytes=2,
        )
