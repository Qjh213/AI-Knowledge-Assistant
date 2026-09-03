import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.core.exceptions import (
    DocumentAlreadyExistsError,
    DocumentNotFoundError,
    DocumentProcessingError,
    DocumentRetryNotAllowedError,
    DocumentTooLargeError,
    EmptyDocumentError,
    KnowledgeBaseAlreadyExistsError,
    KnowledgeBaseNotFoundError,
    UnsupportedDocumentTypeError,
    RetrievalServiceError,
    ChatServiceError,
    ConversationNotFoundError,
)
from app.core.config import settings


logger = logging.getLogger("app.errors")


def service_error_detail(exc: Exception, fallback: str) -> str:
    if settings.is_production or not settings.expose_error_details:
        return fallback
    return str(exc)


async def knowledge_base_not_found_handler(
    request: Request,
    exc: KnowledgeBaseNotFoundError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "detail": str(exc),
            "code": "knowledge_base_not_found",
        },
    )


async def conversation_not_found_handler(
    request: Request,
    exc: ConversationNotFoundError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "detail": str(exc),
            "code": "conversation_not_found",
        },
    )


async def knowledge_base_already_exists_handler(
    request: Request,
    exc: KnowledgeBaseAlreadyExistsError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={
            "detail": str(exc),
            "code": "knowledge_base_already_exists",
        },
    )

async def document_not_found_handler(
    request: Request,
    exc: DocumentNotFoundError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "detail": str(exc),
            "code": "document_not_found",
        },
    )


async def document_already_exists_handler(
    request: Request,
    exc: DocumentAlreadyExistsError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={
            "detail": str(exc),
            "code": "document_already_exists",
        },
    )


async def unsupported_document_type_handler(
    request: Request,
    exc: UnsupportedDocumentTypeError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        content={
            "detail": str(exc),
            "code": "unsupported_document_type",
        },
    )


async def document_too_large_handler(
    request: Request,
    exc: DocumentTooLargeError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
        content={
            "detail": str(exc),
            "code": "document_too_large",
        },
    )


async def empty_document_handler(
    request: Request,
    exc: EmptyDocumentError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "detail": str(exc),
            "code": "empty_document",
        },
    )


async def document_processing_handler(
    request: Request,
    exc: DocumentProcessingError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": service_error_detail(
                exc,
                "Document processing failed. Please retry later.",
            ),
            "code": "document_processing_failed",
        },
    )


async def document_retry_not_allowed_handler(
    request: Request,
    exc: DocumentRetryNotAllowedError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={
            "detail": str(exc),
            "code": "document_retry_not_allowed",
        },
    )


async def retrieval_service_handler(
    request: Request,
    exc: RetrievalServiceError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "detail": service_error_detail(
                exc,
                "Retrieval service is temporarily unavailable.",
            ),
            "code": "retrieval_service_unavailable",
        },
    )


async def chat_service_handler(
    request: Request,
    exc: ChatServiceError,
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "detail": service_error_detail(
                exc,
                "Chat service is temporarily unavailable.",
            ),
            "code": "chat_service_unavailable",
        },
    )


async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    logger.error(
        "Unhandled application exception type=%s", type(exc).__name__,
        extra={"request_id": request_id},
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Internal server error.",
            "code": "internal_server_error",
            "request_id": request_id,
        },
    )


def register_exception_handlers(application: FastAPI) -> None:
    async def validation_error(request: Request, exc: RequestValidationError):
        # Pydantic's default response echoes input, including password fields.
        if '/auth/' in request.url.path or '/admin/' in request.url.path:
            return JSONResponse(status_code=422, content={'detail': '输入格式不正确：用户名需为 3–32 位小写字母、数字或 ._-；新密码需为 12–128 个字符；请检查额度范围。'})
        return JSONResponse(status_code=422, content={'detail': '请求参数格式不正确。'})

    application.add_exception_handler(RequestValidationError, validation_error)
    application.add_exception_handler(
        KnowledgeBaseNotFoundError,
        knowledge_base_not_found_handler,
    )
    application.add_exception_handler(
        ConversationNotFoundError,
        conversation_not_found_handler,
    )
    application.add_exception_handler(
        KnowledgeBaseAlreadyExistsError,
        knowledge_base_already_exists_handler,
    )
    application.add_exception_handler(
        DocumentNotFoundError,
        document_not_found_handler,
    )
    application.add_exception_handler(
        DocumentAlreadyExistsError,
        document_already_exists_handler,
    )
    application.add_exception_handler(
        UnsupportedDocumentTypeError,
        unsupported_document_type_handler,
    )
    application.add_exception_handler(
        DocumentTooLargeError,
        document_too_large_handler,
    )
    application.add_exception_handler(
        EmptyDocumentError,
        empty_document_handler,
    )
    application.add_exception_handler(
        DocumentProcessingError,
        document_processing_handler,
    )
    application.add_exception_handler(
        DocumentRetryNotAllowedError,
        document_retry_not_allowed_handler,
    )
    application.add_exception_handler(
        RetrievalServiceError,
        retrieval_service_handler,
    )
    application.add_exception_handler(
        ChatServiceError,
        chat_service_handler,
    )
    application.add_exception_handler(
        Exception,
        unhandled_exception_handler,
    )
