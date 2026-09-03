import logging
import re
from collections import defaultdict, deque
from threading import Lock
from time import monotonic, perf_counter
from uuid import uuid4

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response


logger = logging.getLogger("app.requests")
SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        incoming_id = request.headers.get("X-Request-ID", "").strip()
        request_id = (
            incoming_id
            if SAFE_REQUEST_ID.fullmatch(incoming_id)
            else uuid4().hex
        )
        request.state.request_id = request_id
        started_at = perf_counter()

        try:
            response = await call_next(request)
        except Exception as exc:
            logger.error(
                "Unhandled request error type=%s", type(exc).__name__,
                extra=self._log_fields(request, request_id, 500, started_at),
            )
            raise

        response.headers["X-Request-ID"] = request_id
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Permissions-Policy", (
            "camera=(), microphone=(), geolocation=()"
        ))
        response.headers.setdefault("Cache-Control", "no-store")
        logger.info(
            "Request completed",
            extra=self._log_fields(
                request,
                request_id,
                response.status_code,
                started_at,
            ),
        )
        return response

    @staticmethod
    def _log_fields(
        request: Request,
        request_id: str,
        status_code: int,
        started_at: float,
    ) -> dict[str, object]:
        forwarded_for = request.headers.get("X-Forwarded-For", "")
        client_ip = (
            forwarded_for.split(",", 1)[0].strip()
            if forwarded_for
            else request.client.host if request.client else "unknown"
        )
        return {
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": status_code,
            "duration_ms": round((perf_counter() - started_at) * 1000, 2),
            "client_ip": client_ip,
        }


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        *,
        requests: int,
        window_seconds: int,
    ) -> None:
        super().__init__(app)
        self.requests = requests
        self.window_seconds = window_seconds
        self._requests_by_client: defaultdict[str, deque[float]] = defaultdict(
            deque
        )
        self._lock = Lock()

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        if request.method == "OPTIONS" or request.url.path.endswith(
            ("/health", "/health/ready")
        ):
            return await call_next(request)

        client_key = request.client.host if request.client else "unknown"
        now = monotonic()
        cutoff = now - self.window_seconds

        with self._lock:
            timestamps = self._requests_by_client[client_key]
            while timestamps and timestamps[0] <= cutoff:
                timestamps.popleft()
            if len(timestamps) >= self.requests:
                retry_after = max(1, int(self.window_seconds - (now - timestamps[0])))
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "detail": "Too many requests. Please try again later.",
                        "code": "rate_limit_exceeded",
                    },
                    headers={"Retry-After": str(retry_after)},
                )
            timestamps.append(now)

        return await call_next(request)
