from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from time import sleep
from typing import Any, Literal
from zipfile import BadZipFile, ZipFile

import httpx

from app.core.config import settings
from app.core.exceptions import MinerUServiceError, MinerUResultDownloadError


MinerUTaskState = Literal[
    "pending",
    "running",
    "converting",
    "done",
    "failed",
]


@dataclass(frozen=True)
class MinerUUploadTask:
    batch_id: str
    upload_url: str


@dataclass(frozen=True)
class MinerUTaskResult:
    batch_id: str
    file_name: str
    state: MinerUTaskState
    progress: int
    full_zip_url: str | None = None
    error_message: str | None = None


class MinerUClient:
    """Small synchronous client for MinerU's official batch API."""

    def __init__(
        self,
        *,
        client: httpx.Client | None = None,
        api_token: str | None = None,
        base_url: str | None = None,
        model_version: Literal["pipeline", "vlm"] | None = None,
        enable_ocr: bool | None = None,
        enable_table: bool | None = None,
        enable_formula: bool | None = None,
    ) -> None:
        self.api_token = (
            settings.secret_value(settings.mineru_api_token)
            if api_token is None
            else api_token
        ).strip()
        self.base_url = (
            settings.mineru_base_url if base_url is None else base_url
        ).rstrip("/")
        self.model_version = model_version or settings.mineru_model_version
        self.enable_ocr = (
            settings.mineru_enable_ocr
            if enable_ocr is None
            else enable_ocr
        )
        self.enable_table = (
            settings.mineru_enable_table
            if enable_table is None
            else enable_table
        )
        self.enable_formula = (
            settings.mineru_enable_formula
            if enable_formula is None
            else enable_formula
        )
        if client is None:
            self.client = httpx.Client(timeout=30.0)
            # Some Windows proxy stacks terminate TLS unexpectedly when
            # downloading from MinerU's result CDN. API calls may still
            # require the configured proxy, so only result downloads bypass
            # proxy environment variables.
            self.download_client = httpx.Client(
                timeout=30.0,
                follow_redirects=True,
                trust_env=False,
            )
        else:
            self.client = client
            self.download_client = client

        if not self.api_token:
            raise MinerUServiceError("MINERU_API_TOKEN is not configured")
        if not self.base_url.startswith("https://"):
            raise MinerUServiceError("MINERU_BASE_URL must use HTTPS")

    def request_upload_url(self, file_name: str) -> MinerUUploadTask:
        safe_name = Path(file_name).name.strip()
        if not safe_name or safe_name != file_name.strip():
            raise MinerUServiceError("invalid upload file name")

        payload = {
            "files": [
                {
                    "name": safe_name,
                    "is_ocr": self.enable_ocr,
                }
            ],
            "model_version": self.model_version,
            "enable_table": self.enable_table,
            "enable_formula": self.enable_formula,
        }
        data = self._request_json(
            "POST",
            "/file-urls/batch",
            json=payload,
        )
        batch_id = self._required_string(data, "batch_id")
        file_urls = data.get("file_urls")
        if not isinstance(file_urls, list) or len(file_urls) != 1:
            raise MinerUServiceError(
                "upload response did not contain exactly one file URL"
            )
        upload_url = file_urls[0]
        if not isinstance(upload_url, str) or not upload_url.startswith(
            "https://"
        ):
            raise MinerUServiceError("upload response contained an invalid URL")
        return MinerUUploadTask(batch_id=batch_id, upload_url=upload_url)

    def upload_file(self, upload_url: str, file_path: Path) -> None:
        path = Path(file_path).resolve()
        if not path.is_file():
            raise MinerUServiceError(f"upload file does not exist: {path}")
        if not upload_url.startswith("https://"):
            raise MinerUServiceError("signed upload URL must use HTTPS")

        try:
            with path.open("rb") as source:
                response = self.client.put(upload_url, content=source)
            response.raise_for_status()
        except (OSError, httpx.HTTPError) as exc:
            raise MinerUServiceError(f"file upload failed: {exc}") from exc

    def get_batch_result(
        self,
        batch_id: str,
        *,
        file_name: str | None = None,
    ) -> MinerUTaskResult:
        normalized_batch_id = batch_id.strip()
        if not normalized_batch_id:
            raise MinerUServiceError("batch ID cannot be empty")

        data = self._request_json(
            "GET",
            f"/extract-results/batch/{normalized_batch_id}",
        )
        results = data.get("extract_result")
        if not isinstance(results, list) or not results:
            raise MinerUServiceError("task response did not contain results")

        result = self._select_result(results, file_name)
        state = result.get("state")
        valid_states = {"pending", "running", "converting", "done", "failed"}
        if state not in valid_states:
            raise MinerUServiceError(f"unknown MinerU task state: {state!r}")

        progress = self._progress(result, state)
        returned_name = result.get("file_name") or file_name or ""
        if not isinstance(returned_name, str):
            returned_name = str(returned_name)

        zip_url = result.get("full_zip_url")
        if zip_url is not None and not isinstance(zip_url, str):
            raise MinerUServiceError("task response contained an invalid ZIP URL")
        error_message = result.get("err_msg")
        if error_message is not None and not isinstance(error_message, str):
            error_message = str(error_message)

        return MinerUTaskResult(
            batch_id=normalized_batch_id,
            file_name=returned_name,
            state=state,
            progress=progress,
            full_zip_url=zip_url,
            error_message=error_message,
        )

    def download_markdown(
        self,
        full_zip_url: str,
        *,
        max_download_bytes: int = 100 * 1024 * 1024,
        max_markdown_bytes: int = 20 * 1024 * 1024,
    ) -> str:
        """Download a MinerU result archive and return its full.md text."""
        if not full_zip_url.startswith("https://"):
            raise MinerUServiceError("result ZIP URL must use HTTPS")
        if max_download_bytes <= 0 or max_markdown_bytes <= 0:
            raise MinerUServiceError("download size limits must be positive")

        for attempt in range(3):
            # Discard partial data before retrying a read-only download.
            archive = bytearray()
            try:
                with self.download_client.stream("GET", full_zip_url) as response:
                    response.raise_for_status()
                    for chunk in response.iter_bytes():
                        archive.extend(chunk)
                        if len(archive) > max_download_bytes:
                            raise MinerUServiceError(
                                "result ZIP exceeded the download size limit"
                            )
                break
            except httpx.HTTPError as exc:
                if attempt < 2 and self._retryable_read_error(exc):
                    sleep(2 ** attempt)
                    continue
                # Never expose signed URLs in the user-visible message.
                reason = (
                    f"HTTP {exc.response.status_code}"
                    if isinstance(exc, httpx.HTTPStatusError)
                    else type(exc).__name__
                )
                raise MinerUResultDownloadError(
                    f"MinerU 已完成解析，但结果 ZIP 下载失败（{reason}，尝试 {attempt + 1} 次）。"
                    "请检查下载站的网络或代理配置后重试。"
                ) from exc

        try:
            with ZipFile(BytesIO(archive)) as result_zip:
                matches = [
                    item
                    for item in result_zip.infolist()
                    if not item.is_dir()
                    and Path(item.filename).name.casefold() == "full.md"
                ]
                if len(matches) != 1:
                    raise MinerUServiceError(
                        "result ZIP must contain exactly one full.md"
                    )
                markdown_info = matches[0]
                if markdown_info.file_size > max_markdown_bytes:
                    raise MinerUServiceError(
                        "full.md exceeded the extracted size limit"
                    )
                markdown_bytes = result_zip.read(markdown_info)
        except MinerUServiceError:
            raise
        except (BadZipFile, OSError, RuntimeError) as exc:
            raise MinerUServiceError(
                f"invalid MinerU result ZIP: {exc}"
            ) from exc

        try:
            markdown = markdown_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise MinerUServiceError("full.md was not UTF-8 encoded") from exc
        if not markdown.strip():
            raise MinerUServiceError("full.md did not contain extractable text")
        return markdown

    def _request_json(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        headers = dict(kwargs.pop("headers", {}))
        headers["Authorization"] = f"Bearer {self.api_token}"
        attempts = 3 if method.upper() == "GET" else 1
        for attempt in range(attempts):
            try:
                response = self.client.request(
                    method, f"{self.base_url}{path}", headers=headers, **kwargs
                )
                response.raise_for_status()
                payload = response.json()
                break
            except (httpx.HTTPError, ValueError) as exc:
                if attempt < attempts - 1 and self._retryable_read_error(exc):
                    sleep(2 ** attempt)
                    continue
                raise MinerUServiceError(
                    f"API request failed ({type(exc).__name__}); check network and credentials"
                ) from exc

        if not isinstance(payload, dict):
            raise MinerUServiceError("API response was not a JSON object")
        if payload.get("code") != 0:
            message = payload.get("msg") or "unknown MinerU API error"
            raise MinerUServiceError(str(message))
        data = payload.get("data")
        if not isinstance(data, dict):
            raise MinerUServiceError("API response did not contain data")
        return data

    @staticmethod
    def _retryable_read_error(error: Exception) -> bool:
        if isinstance(error, httpx.HTTPStatusError):
            return error.response.status_code in {408, 429, 500, 502, 503, 504}
        if "CERTIFICATE_VERIFY_FAILED" in str(error):
            return False
        return isinstance(error, httpx.TransportError)

    @staticmethod
    def _required_string(data: dict[str, Any], key: str) -> str:
        value = data.get(key)
        if not isinstance(value, str) or not value.strip():
            raise MinerUServiceError(f"API response omitted {key}")
        return value.strip()

    @staticmethod
    def _select_result(
        results: list[Any],
        file_name: str | None,
    ) -> dict[str, Any]:
        valid_results = [item for item in results if isinstance(item, dict)]
        if file_name is None:
            if len(valid_results) != 1:
                raise MinerUServiceError(
                    "file name is required for a multi-file batch"
                )
            return valid_results[0]

        for item in valid_results:
            if item.get("file_name") == file_name:
                return item
        raise MinerUServiceError(
            f"task response did not contain file '{file_name}'"
        )

    @staticmethod
    def _progress(result: dict[str, Any], state: str) -> int:
        if state == "done":
            return 100
        if state == "failed":
            return 0
        progress = result.get("extract_progress")
        if not isinstance(progress, dict):
            return 0
        extracted = progress.get("extracted_pages")
        total = progress.get("total_pages")
        if not isinstance(extracted, int) or not isinstance(total, int):
            return 0
        if total <= 0:
            return 0
        return max(0, min(99, round(extracted / total * 100)))
